import asyncio
import time
import requests
import structlog
from fastapi import HTTPException

from src.models.enum import WorkerStatus
from ...models.basemodels import QuestionConfig, WorkerNode, LLMResponse
from ..util.cluster_config import config_store
from threading import Lock
from ...custom_logging.logger import log_node_status_snapshot
from ...models.test_state import test_state
import math

worker_lock = Lock()  # Cannot have any race conditions

logger = structlog.get_logger()

rr_index = 0

#TODO måske lige prøve at teste en ny model sådan man får nogleunde svar tilbage igen. 
def round_robin(workers: list[WorkerNode]) -> WorkerNode | None:
    """Pick a worker in round-robin order."""
    global rr_index
    if not workers:
        return None

    workers = sorted(workers, key=lambda worker: worker.name)  # sort based on node/worker name
    worker = workers[rr_index % len(workers)]
    rr_index += 1
    return worker


def choose_worker_node(worker_node_list: list[WorkerNode]) -> WorkerNode | None:
    """Choose a node based on the slots available."""
    if not worker_node_list:
        return None

    eligible_workers = [
        worker for worker in worker_node_list
        if worker.status in {WorkerStatus.IDLE, WorkerStatus.WORKING}
    ]

    if not eligible_workers:
        return None

    # 1. Prefer an idle worker
    idle_workers = [
        worker for worker in eligible_workers
        if worker.inflight_requests == 0
    ]
    if idle_workers:
        # Choose the first worker by name.
        # Keeping the selection stable helps leave other workers idle so
        # the power scheduler can do its job.
        return sorted(idle_workers, key=lambda worker: worker.name)[0]

    # 2. Otherwise prefer workers with the most free slots
    best_free_slots = max(worker.free_slots for worker in eligible_workers)

    best_workers = [
        worker for worker in eligible_workers
        if worker.free_slots == best_free_slots
    ]

    if len(best_workers) == 1:
        return best_workers[0]

    # 3. If there are multiple with the same free slots (above 0), just pick the first one
    if best_free_slots > 0:
        return sorted(best_workers, key=lambda worker: worker.name)[0]

    # 4. Only round robin when all best workers are full or overloaded
    return round_robin(best_workers)


def sync_worker_status(worker: WorkerNode) -> None:
    """Sync the status of the worker."""
    cluster = config_store.get()
    cluster_name = cluster.cluster_config.name
    worker.status = WorkerStatus.IDLE if worker.inflight_requests == 0 else WorkerStatus.WORKING
    log_node_status_snapshot(cluster_name, worker)


def handle_llm(question: QuestionConfig, trace_id: str | None = None):
    """Send the request to the correct working node and log."""

    config = None
    cluster_name = None
    worker_node = None
    trace_id = trace_id
    start_time = time.monotonic()
    if test_state.is_stopping():
            logger.info(
                "cluster_api.llm.rejected_stopping",
                service="cluster_api",
                trace_id=trace_id,
            )
            raise HTTPException(status_code=409, detail="Cluster is stopping")

    try:

        config = config_store.get()
        cluster_name = config.cluster_config.name

        logger.info(
            "cluster_api.llm.request_started",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=None,
            trace_id=trace_id,
            worker_count=len(config.worker_nodes),
        )

        with worker_lock:
            if test_state.is_stopping():
                raise HTTPException(status_code=503, detail="Cluster is stopping")
            for worker in config.worker_nodes:
                sync_worker_status(worker)

            worker_node = choose_worker_node(config.worker_nodes)
            if worker_node is None:
                logger.error(
                    "cluster_api.llm.no_available_worker",
                    cluster_name=cluster_name,
                    worker_node=None,
                    worker_count=len(config.worker_nodes),
                )
                raise HTTPException(status_code=503, detail="No available worker")

            worker_node.inflight_requests += 1
            sync_worker_status(worker_node)
            inflight_at_selection = worker_node.inflight_requests
            active_at_selection = worker_node.active_requests
            queued_at_selection = worker_node.queued_requests
            free_slots_after = worker_node.free_slots
            max_slots_at_selection = worker_node.max_slots

            if config.cluster_config.k3d:
                target_port = worker_node.forwarded_port
            else:
                target_port = config.cluster_config.llama_hostport
            logger.info(
                "cluster_api.llm.worker_selected",
                service="cluster_api",
                cluster_name=cluster_name,
                worker_node=worker_node.name,
                worker_ip=worker_node.ip,
                target_port=target_port,
                status_after=worker_node.status,
                inflight_after=worker_node.inflight_requests,
                active_after=worker_node.active_requests,
                queued_after=worker_node.queued_requests,
                max_slots=worker_node.max_slots,
                free_slots_after=free_slots_after,
            )

        if config.cluster_config.k3d:
            url = f"http://localhost:{worker_node.forwarded_port}/completion"
        else:
            url = f"http://{worker_node.ip}:{config.cluster_config.llama_hostport}/completion"

        payload = {
            "prompt": f"Question: {question.question} Answer:",
            "n_predict": question.max_output_tokens,
            "temperature": 0.2, 
        }


        if test_state.is_stopping():
            logger.info(
                "cluster_api.llm.rejected_before_worker_forward",
                service="cluster_api",
                cluster_name=cluster_name,
                worker_node=worker_node.name,
                trace_id=trace_id,
            )
            raise HTTPException(status_code=409, detail="Cluster is stopping")



        cluster_queue_time_ms = int((time.monotonic() - start_time) * 1000)
        llama_call_start = time.monotonic()
        #TODO async
        if test_state.is_stopping():
            raise HTTPException(status_code=503, detail="Cluster is stopping")
        logger.info(
            "cluster_api.llm.llama_inference_started",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            trace_id=trace_id,
            target_url=url,
        )
        
        BASE_GENERATION_TIMEOUT_S = 120
        QUEUE_WAVE_TIMEOUT_S = 120
        SAFETY_BUFFER_S = 30

        requests_ahead = max(0, inflight_at_selection - 1)
        waves_ahead = math.ceil(requests_ahead / max(1, max_slots_at_selection))

        timeout = (
            BASE_GENERATION_TIMEOUT_S
            + waves_ahead * QUEUE_WAVE_TIMEOUT_S
            + SAFETY_BUFFER_S
        )

        response = requests.post(
            url,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()

        cluster_llama_inference_ms = int((time.monotonic() - llama_call_start) * 1000)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "cluster_api.llm.request_succeeded",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            trace_id=trace_id,
            worker_ip=worker_node.ip,
            target_url=url,
            cluster_llama_inference_ms=cluster_llama_inference_ms,
            cluster_total_time_ms=duration_ms,
            status_code=response.status_code,
            max_output_tokens=question.max_output_tokens,
        )
        result = response.json()

        return LLMResponse(
            llm_content=result,
            worker_node=worker_node,
            inflight_requests_at_selection=inflight_at_selection,
            active_requests_at_selection=active_at_selection,
            queued_requests_at_selection=queued_at_selection,
            max_slots=max_slots_at_selection,
            cluster_queue_time_ms=cluster_queue_time_ms,
            cluster_llama_inference_ms=cluster_llama_inference_ms,
            llama_response_status_code=response.status_code,
        )

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)

        logger.exception(
            "cluster_api.llm.request_failed",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=worker_node.name if worker_node else None,
            trace_id=trace_id,
            worker_ip=worker_node.ip if worker_node else None,
            cluster_total_time_ms=duration_ms,
            error=str(e),
        )
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=502, detail=f"LLM request failed: {str(e)}") from e

    finally:
        # No matter whether it failed or succeded, we still need to free the slot
        if worker_node is not None:
            with worker_lock:

                worker_node.inflight_requests = max(0, worker_node.inflight_requests - 1)
                sync_worker_status(worker_node)

                logger.info(
                    "cluster_api.llm.worker_released",
                    service="cluster_api",
                    cluster_name=cluster_name,
                    worker_node=worker_node.name,
                    trace_id=trace_id,
                    worker_ip=worker_node.ip,
                    status_after=worker_node.status,
                    inflight_after=worker_node.inflight_requests,
                    active_after=worker_node.active_requests,
                    queued_after=worker_node.queued_requests,
                    max_slots=worker_node.max_slots,
                    free_slots_after=worker_node.free_slots,
                )


# Async lock — replaces the threading.Lock for the async version.
# Same critical section semantics; safe to await inside.
_worker_lock_async = asyncio.Lock()

async def handle_llm_async(question: QuestionConfig, trace_id: str | None = None):
    """Async version of handle_llm. Doesn't consume a thread."""

    config = None
    cluster_name = None
    worker_node = None
    start_time = time.monotonic()

    if test_state.is_stopping():
        logger.info(
            "cluster_api.llm.rejected_stopping",
            service="cluster_api",
            trace_id=trace_id,
        )
        raise HTTPException(status_code=409, detail="Cluster is stopping")

    try:
        config = config_store.get()
        cluster_name = config.cluster_config.name

        logger.info(
            "cluster_api.llm.request_started",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=None,
            trace_id=trace_id,
            worker_count=len(config.worker_nodes),
        )

        async with _worker_lock_async:
            if test_state.is_stopping():
                raise HTTPException(status_code=503, detail="Cluster is stopping")

            for worker in config.worker_nodes:
                sync_worker_status(worker)

            worker_node = choose_worker_node(config.worker_nodes)
            if worker_node is None:
                logger.error(
                    "cluster_api.llm.no_available_worker",
                    cluster_name=cluster_name,
                    worker_node=None,
                    worker_count=len(config.worker_nodes),
                )
                raise HTTPException(status_code=503, detail="No available worker")

            worker_node.inflight_requests += 1
            sync_worker_status(worker_node)
            inflight_at_selection = worker_node.inflight_requests
            active_at_selection = worker_node.active_requests
            queued_at_selection = worker_node.queued_requests
            free_slots_after = worker_node.free_slots
            max_slots_at_selection = worker_node.max_slots

            if config.cluster_config.k3d:
                target_port = worker_node.forwarded_port
            else:
                target_port = config.cluster_config.llama_hostport

            logger.info(
                "cluster_api.llm.worker_selected",
                service="cluster_api",
                cluster_name=cluster_name,
                worker_node=worker_node.name,
                worker_ip=worker_node.ip,
                target_port=target_port,
                status_after=worker_node.status,
                inflight_after=worker_node.inflight_requests,
                active_after=worker_node.active_requests,
                queued_after=worker_node.queued_requests,
                max_slots=worker_node.max_slots,
                free_slots_after=free_slots_after,
            )

        if config.cluster_config.k3d:
            url = f"http://localhost:{worker_node.forwarded_port}/completion"
        else:
            url = f"http://{worker_node.ip}:{config.cluster_config.llama_hostport}/completion"

        payload = {
            "prompt": f"Question: {question.question} Answer:",
            "n_predict": question.max_output_tokens,
            "temperature": 0.2,
        }

        if test_state.is_stopping():
            logger.info(
                "cluster_api.llm.rejected_before_worker_forward",
                service="cluster_api",
                cluster_name=cluster_name,
                worker_node=worker_node.name,
                trace_id=trace_id,
            )
            raise HTTPException(status_code=409, detail="Cluster is stopping")

        cluster_queue_time_ms = int((time.monotonic() - start_time) * 1000)
        llama_call_start = time.monotonic()

        if test_state.is_stopping():
            raise HTTPException(status_code=503, detail="Cluster is stopping")

        logger.info(
            "cluster_api.llm.llama_inference_started",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            trace_id=trace_id,
            target_url=url,
        )

        BASE_GENERATION_TIMEOUT_S = 120
        QUEUE_WAVE_TIMEOUT_S = 120
        SAFETY_BUFFER_S = 30

        requests_ahead = max(0, inflight_at_selection - 1)
        waves_ahead = math.ceil(requests_ahead / max(1, max_slots_at_selection))

        timeout_s = (
            BASE_GENERATION_TIMEOUT_S
            + waves_ahead * QUEUE_WAVE_TIMEOUT_S
            + SAFETY_BUFFER_S
        )
        timeout = aiohttp.ClientTimeout(total=timeout_s)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                status_code = response.status

        cluster_llama_inference_ms = int((time.monotonic() - llama_call_start) * 1000)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        logger.info(
            "cluster_api.llm.request_succeeded",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            trace_id=trace_id,
            worker_ip=worker_node.ip,
            target_url=url,
            cluster_llama_inference_ms=cluster_llama_inference_ms,
            cluster_total_time_ms=duration_ms,
            status_code=status_code,
            max_output_tokens=question.max_output_tokens,
        )

        return LLMResponse(
            llm_content=result,
            worker_node=worker_node,
            inflight_requests_at_selection=inflight_at_selection,
            active_requests_at_selection=active_at_selection,
            queued_requests_at_selection=queued_at_selection,
            max_slots=max_slots_at_selection,
            cluster_queue_time_ms=cluster_queue_time_ms,
            cluster_llama_inference_ms=cluster_llama_inference_ms,
            llama_response_status_code=status_code,
        )

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)

        logger.exception(
            "cluster_api.llm.request_failed",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=worker_node.name if worker_node else None,
            trace_id=trace_id,
            worker_ip=worker_node.ip if worker_node else None,
            cluster_total_time_ms=duration_ms,
            error=str(e),
        )
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=502, detail=f"LLM request failed: {str(e)}") from e

    finally:
        if worker_node is not None:
            async with _worker_lock_async:
                worker_node.inflight_requests = max(0, worker_node.inflight_requests - 1)
                sync_worker_status(worker_node)

                logger.info(
                    "cluster_api.llm.worker_released",
                    service="cluster_api",
                    cluster_name=cluster_name,
                    worker_node=worker_node.name,
                    trace_id=trace_id,
                    worker_ip=worker_node.ip,
                    status_after=worker_node.status,
                    inflight_after=worker_node.inflight_requests,
                    active_after=worker_node.active_requests,
                    queued_after=worker_node.queued_requests,
                    max_slots=worker_node.max_slots,
                    free_slots_after=worker_node.free_slots,
                )