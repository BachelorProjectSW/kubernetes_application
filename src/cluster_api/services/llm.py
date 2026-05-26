import time
import requests
import structlog
from fastapi import HTTPException

from src.models.enum import WorkerStatus
from ...models.basemodels import QuestionConfig, WorkerNode, LLMResponse
from ..util.cluster_config import config_store
from threading import Lock
from ...custom_logging.logger import log_node_status_snapshot

worker_lock = Lock()  # Cannot have any race conditions

logger = structlog.get_logger()

rr_index = 0


def round_robin(workers: list[WorkerNode]) -> WorkerNode | None:
    """Pick a worker using simple round-robin selection.

    Simple explanation:
    - Keep a global index and return the worker at `index % len(workers)`.
    - This gives a fair, predictable rotation when all other selection rules don't apply.

    Args:
        workers: List of available `WorkerNode` objects to rotate through.

    Returns:
        A `WorkerNode` chosen by round-robin, or `None` if the input list is empty.

    """
    global rr_index
    if not workers:
        return None

    workers = sorted(workers, key=lambda worker: worker.name)  # sort based on node/worker name
    worker = workers[rr_index % len(workers)]
    rr_index += 1
    return worker


def choose_worker_node(worker_node_list: list[WorkerNode]) -> WorkerNode | None:
    """Choose the best worker node to handle a request.

    1. Ignore nodes that are powered off or otherwise unavailable.
    2. Prefer an idle node (zero inflight requests) to keep others ready for power scheduling.
    3. If no idle node, pick the node with the most free slots.
    4. If multiple nodes tie on free slots, pick deterministically by name.
    5. If all tied nodes have zero free slots (all busy), fall back to round-robin.

    Args:
        worker_node_list: Full list of `WorkerNode` objects for this cluster to choose from.

    Returns:
        The selected `WorkerNode`, or `None` when no eligible worker exists.

    """
    # Note: keeping selection deterministic (sorted by name) helps debugging and reduces
    # unnecessary churn between workers which can interfere with power/latency decisions.
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
    """Update a worker's `status` to reflect its current inflight requests.

    Simple explanation:
    - Do not override power-transition states (OFF, TURNING_ON, TURNING_OFF).
    - If the node has zero inflight requests set it to `IDLE`, otherwise `WORKING`.

    Args:
        worker: The `WorkerNode` to update in-place based on inflight request count.

    Returns:
        None. The function mutates the `worker` object and logs the status snapshot.

    """
    if worker.status in {WorkerStatus.OFF, WorkerStatus.TURNING_ON, WorkerStatus.TURNING_OFF}:
        return

    cluster = config_store.get()
    cluster_name = cluster.cluster_config.name
    worker.status = WorkerStatus.IDLE if worker.inflight_requests == 0 else WorkerStatus.WORKING
    log_node_status_snapshot(cluster_name, worker)


def handle_llm(question: QuestionConfig, trace_id: str | None = None):
    """Send a single LLM question to a selected worker and return the response.

    Purpose:
    - Pick a worker using the selection rules, increment its inflight counter,
    - Call the worker's Llama `/completion` endpoint, gather timings and logs,
    - Return an `LLMResponse` wrapper with metadata about the selected worker and timings.

    Important operational notes for readers:
    - A `worker_lock` is used to avoid races when selecting and updating worker counters.
    - The selected worker's `inflight_requests` is incremented before the external call
      and always decremented in the `finally` block so slots are never leaked.
    - The code distinguishes `k3d` (local test) vs production by using forwarded ports.
    - Timeouts are computed conservatively based on queued requests so long-running
      model calls don't block forever.

    Args:
        question: `QuestionConfig` containing the question text and max output tokens.
        trace_id: Optional trace id extracted from the HTTP request headers for logging.

    Returns:
        An `LLMResponse` object containing the raw LLM result plus selection/timing metadata.

    Raises:
        `HTTPException(503)` if no worker is available, or
        `HTTPException(502)` if the LLM request failed for other reasons.

    """
    # Keep local variables initialized for clear error logging below.
    try:
        config = None
        cluster_name = None
        worker_node = None
        trace_id = trace_id
        start_time = time.monotonic()

        config = config_store.get()
        cluster_name = config.cluster_config.name

        logger.debug(
            "cluster_api.llm.request_started",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=None,
            trace_id=trace_id,
            worker_count=len(config.worker_nodes),
        )

        with worker_lock:
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
            logger.debug(
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

        cluster_queue_time_ms = int((time.monotonic() - start_time) * 1000)
        llama_call_start = time.monotonic()
        logger.debug(
            "cluster_api.llm.llama_inference_started",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            trace_id=trace_id,
            target_url=url,
        )
        timeout = 180 + (queued_at_selection * 90)

        response = requests.post(
            url,
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()

        cluster_llama_inference_ms = int((time.monotonic() - llama_call_start) * 1000)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.debug(
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
        llama_status_code = getattr(getattr(e, "response", None), "status_code", None)

        logger.exception(
            "cluster_api.llm.request_failed",
            service="cluster_api",
            cluster_name=cluster_name,
            worker_node=worker_node.name if worker_node else None,
            trace_id=trace_id,
            worker_ip=worker_node.ip if worker_node else None,
            cluster_total_time_ms=duration_ms,
            llama_status_code=llama_status_code,
            error=str(e),
        )
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=502,
            detail=f"LLM request failed: {str(e)} (llama_status={llama_status_code})",
        ) from e

    finally:
        # No matter whether it failed or succeded, we still need to free the slot
        if worker_node is not None:
            with worker_lock:

                worker_node.inflight_requests = max(0, worker_node.inflight_requests - 1)
                sync_worker_status(worker_node)

                logger.debug(
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
