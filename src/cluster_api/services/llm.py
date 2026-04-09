import time
import requests
import structlog

from ...models.basemodels import QuestionConfig, WorkerNode
from ..util.cluster_config import config_store

from threading import Lock
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
        if worker.status in {"idle", "working"}
    ]

    if not eligible_workers:
        return None

    # 1. Prefer an idle worker
    idle_workers = [worker for worker in eligible_workers if worker.slots_in_use == 0]
    if idle_workers:
        return sorted(idle_workers, key=lambda worker: worker.name)[0]

    # 2. Otherwise prefer workers with the most free slots
    best_free_slots = max(
        worker.max_slots - worker.slots_in_use
        for worker in eligible_workers
    )

    best_workers = [
        worker for worker in eligible_workers
        if (worker.max_slots - worker.slots_in_use) == best_free_slots
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
    worker.status = "idle" if worker.slots_in_use == 0 else "working"


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

            slots_before = worker_node.slots_in_use
            status_before = worker_node.status

            worker_node.slots_in_use += 1
            sync_worker_status(worker_node)

            logger.info(
                "worker.worker_selected",
                worker_name=worker_node.name,
                worker_ip=worker_node.ip,
                status_before=status_before,
                status_after=worker_node.status,
                slots_before=slots_before,
                slots_after=worker_node.slots_in_use,
                max_slots=worker_node.max_slots,
                free_slots_before=worker_node.max_slots - slots_before,
                free_slots_after=worker_node.max_slots - worker_node.slots_in_use,
            )

        if config.cluster_config.use_port_forward:
            url = f"http://localhost:{config.cluster_config.llama_service_port}/completion"
        else:
            url = f"http://{worker_node.ip}:{config.cluster_config.llama_nodeport}/completion"

        payload = {
            "prompt": question.question,
            "n_predict": question.max_output_tokens,
            "temperature": 0,
        }

        response = requests.post(
            url,
            json=payload,
            timeout=60,
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
            prompt_length=len(question.question) if question.question else 0,
        )

        return response.json()

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
                slots_before = worker_node.slots_in_use
                status_before = worker_node.status

                worker_node.slots_in_use = max(0, worker_node.slots_in_use - 1)
                sync_worker_status(worker_node)

                logger.info(
                    "worker.worker_released",
                    worker_name=worker_node.name,
                    worker_ip=worker_node.ip,
                    status_before=status_before,
                    status_after=worker_node.status,
                    slots_before=slots_before,
                    slots_after=worker_node.slots_in_use,
                    max_slots=worker_node.max_slots,
                    free_slots_after=worker_node.max_slots - worker_node.slots_in_use,
                )
