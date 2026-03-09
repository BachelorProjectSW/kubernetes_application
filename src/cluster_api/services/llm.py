import time
import requests
import structlog

from src.models.enum import WorkerStatus
from ...models.basemodels import QuestionConfig, WorkerNode, LLMResponse
from ..util.cluster_config import config_store
from threading import Lock
from ...custom_logging.logger import log_node_status_snapshot

worker_lock = Lock()  # Cannot have any race conditions

logger = structlog.get_logger()

rr_index = 0


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


def handle_llm(question: QuestionConfig):
    """Send the request to the correct working node and log."""
    config = None
    worker_node = None
    start_time = time.monotonic()

    try:
        config = config_store.get()

        with worker_lock:
            for worker in config.worker_nodes:
                sync_worker_status(worker)

            worker_node = choose_worker_node(config.worker_nodes)
            if worker_node is None:
                logger.error(
                    "worker.no_available_worker",
                    worker_count=len(config.worker_nodes),
                )
                return "failed: no available worker"

            worker_node.inflight_requests += 1
            sync_worker_status(worker_node)
            inflight_at_selection = worker_node.inflight_requests
            active_at_selection = worker_node.active_requests
            queued_at_selection = worker_node.queued_requests
            free_slots_after = worker_node.free_slots
            max_slots_at_selection = worker_node.max_slots

            logger.info(
                "worker.worker_selected",
                worker_name=worker_node.name,
                worker_ip=worker_node.ip,
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
            "prompt": question.question,
            "n_predict": question.max_output_tokens,
            "temperature": 0,
        }

        response = requests.post(
            url,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "worker.llm_request_succeeded",
            worker_name=worker_node.name,
            worker_ip=worker_node.ip,
            duration_ms=duration_ms,
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
        )

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)

        logger.exception(
            "worker.llm_request_failed",
            worker_name=worker_node.name if worker_node else None,
            worker_ip=worker_node.ip if worker_node else None,
            duration_ms=duration_ms,
            error=str(e),
        )
        return f"failed: {e}"

    finally:
        # No matter whether it failed or succeded, we still need to free the slot
        if worker_node is not None:
            with worker_lock:

                worker_node.inflight_requests = max(0, worker_node.inflight_requests - 1)
                sync_worker_status(worker_node)

                logger.info(
                    "worker.worker_released",
                    worker_name=worker_node.name,
                    worker_ip=worker_node.ip,
                    status_after=worker_node.status,
                    inflight_after=worker_node.inflight_requests,
                    active_after=worker_node.active_requests,
                    queued_after=worker_node.queued_requests,
                    max_slots=worker_node.max_slots,
                    free_slots_after=worker_node.free_slots,
                )
