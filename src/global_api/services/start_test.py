import time

from fastapi import HTTPException

from ...cluster_api.services.power_scheduler import run_cmd

from ...models.basemodels import Config, ClusterInformation
from ..util.all_configuration import config_store
from ...custom_logging.logger import set_current_config_id
import requests
import structlog
from .power_scheduler import power_scheduler_loop
import asyncio
import threading
from .ensure_nodes_ready import ensure_nodes_ready
from ..services.test_state import test_state
from ...models.enum import WorkerStatus


_power_scheduler_thread: threading.Thread | None = None
log = structlog.get_logger()


def _run_power_scheduler_loop():
    """Run the async power scheduler in a dedicated thread."""
    asyncio.run(power_scheduler_loop())


def start_test(config: Config):
    """Start the test and send configs."""
    if test_state.is_running():
        raise HTTPException(status_code=409, detail="A test is already running")
    started = False
    try:
        global _power_scheduler_thread
        set_current_config_id(config.id)
        config_store.set(config)
        
        log.info("global_api.test.start_requested", config_id=config.id, test_name=config.name)
        # TODO set start_time_real = current time datetime.now().strf()

        for cluster in config.clusters:
            cluster_information = ClusterInformation(
                config_id=config.id,
                cluster_config=cluster,
                question_config=config.question,
                worker_nodes=[]
            )
            ip = cluster.ip
            port = cluster.port
            url = f"http://{ip}:{port}/set_config"

            log.info(
                "global_api.test.cluster_config_push_started",
                cluster_name=cluster.name,
                target_url=url,
            )
            response = requests.post(url, json=cluster_information.model_dump(), timeout=30)
            response.raise_for_status()
            log.info(
                "global_api.test.cluster_config_push_succeeded",
                cluster_name=cluster.name,
                status_code=response.status_code,
            )
            # ensure that all nodes + pods are on and ready to recieve requests
            ensure_nodes_ready(cluster, timeout_s=400)

        if config.power_scheduler.start:
            thread_running = (
                _power_scheduler_thread is not None
                and _power_scheduler_thread.is_alive()
            )
            if not thread_running:
                _power_scheduler_thread = threading.Thread(
                    target=_run_power_scheduler_loop,
                    daemon=True,
                    name="global-power-scheduler",
                )
                _power_scheduler_thread.start()
                log.info("global_api.test.power_scheduler_started")
        name = config.name
        test_state.start()
        started = True
        log.info("global_api.test.start_completed", config_id=config.id, test_name=name)
        return f"{name} test are running succesfully"
    except HTTPException:
        log.warning("global_api.test.start_rejected")
        raise
    except Exception as e:
        if not started:
            test_state.reset()
        log.exception("global_api.test.start_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"test failed: {e}")


def stop_cancel_recover_cluster(cluster, errors: list[tuple[str, Exception]]):
    try:
        stop_cluster(cluster)
        cancel_cluster_pods(cluster)
        recover_cluster_after_stop(cluster, timeout_s=400)
    except Exception as e:
        errors.append((cluster.name, e))


def stop_test():
    if test_state.is_stopping():
        return {"message": "Stop already in progress"}

    if not test_state.is_running():
        return {"message": "No test running"}

    config = config_store.get()
    test_state.mark_stopping()
    config_store.stop_power_scheduler()

    if not config:
        test_state.reset()
        return {"message": "Stop completed"}

    errors = []
    threads = []

    for cluster in config.clusters:
        thread = threading.Thread(
            target=stop_cancel_recover_cluster,
            args=(cluster, errors),
            name=f"stop-cancel-recover-{cluster.name}",
        )
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    if errors:
        for cluster_name, error in errors:
            log.error(
                "global.stop_test.cluster_recovery_failed",
                cluster=cluster_name,
                error=str(error),
            )

        # Important: do NOT reset to idle if recovery failed.
        raise HTTPException(
            status_code=500,
            detail=f"Stop recovery failed for clusters: {[name for name, _ in errors]}",
        )

    test_state.reset()
    log.info("global.stop_test.done", had_config=True, recovered=True)
    return {"message": "Stop completed"}
def cancel_cluster_pods(cluster) -> bool:
    try:
        response = requests.post(
            f"http://{cluster.ip}:{cluster.port}/cancel_all_llama_pods",
            timeout=5,
        )
        response.raise_for_status()
        log.info(
            "global.stop_test.cluster_cancel_requested",
            cluster=cluster.name,
            status_code=response.status_code,
        )
        return True
    except Exception as e:
        log.warning(
            "global.stop_test.cluster_cancel_failed",
            cluster=cluster.name,
            error=str(e),
        )   
        return False
    
def stop_cluster(cluster):
    try:
        response = requests.post(
            f"http://{cluster.ip}:{cluster.port}/stop_test",
            timeout=5,
        )
        response.raise_for_status()
        log.info(
            "global.stop_test.cluster_stop_requested",
            cluster=cluster.name,
            status_code=response.status_code,
        )
    except Exception as e:
        log.warning(
            "global.stop_test.cluster_stop_failed",
            cluster=cluster.name,
            error=str(e),
        )

def recover_cluster_after_stop(
    cluster,
    timeout_s: int = 400,
    poll_interval_s: int = 5,
):
    base = f"http://{cluster.ip}:{cluster.port}"
    deadline = time.time() + timeout_s

    expected_total = None

    while time.time() < deadline:
        try:
            info = requests.get(
                f"{base}/get_cluster_information",
                timeout=10,
            ).json()

            nodes = info.get("worker_nodes", [])
            expected_total = len(nodes)

            pods_response = requests.get(
                f"{base}/llama_pods_status",
                timeout=10,
            )
            pods_response.raise_for_status()
            pods = pods_response.json()

            live_ready_pods = [
                pod for pod in pods
                if pod["phase"] == "Running"
                and pod["ready"] is True
                and pod["deletion_timestamp"] is None
            ]

            terminating_or_unknown_pods = [
                pod for pod in pods
                if pod["deletion_timestamp"] is not None
                or pod["phase"] in {"Failed", "Unknown"}
            ]

            if len(live_ready_pods) != expected_total:
                log.info(
                    "recover_cluster_after_stop.waiting_for_ready_pods",
                    cluster=cluster.name,
                    live_ready_pods=len(live_ready_pods),
                    expected_total=expected_total,
                    bad_pods=len(terminating_or_unknown_pods),
                )
                time.sleep(poll_interval_s)
                continue

            if terminating_or_unknown_pods:
                log.info(
                    "recover_cluster_after_stop.waiting_for_old_pods_to_disappear",
                    cluster=cluster.name,
                    bad_pods=[pod["name"] for pod in terminating_or_unknown_pods],
                )
                time.sleep(poll_interval_s)
                continue

            refresh_response = requests.post(
                f"{base}/refresh_worker_capacities",
                timeout=30,
            )
            refresh_response.raise_for_status()

            working_response = requests.get(
                f"{base}/get_cluster_working_nodes",
                timeout=10,
            )
            working_response.raise_for_status()
            worker_nodes = working_response.json()

            ready_workers = [
                node for node in worker_nodes
               if node.get("status") == WorkerStatus.IDLE
            ]

            if len(ready_workers) != expected_total:
                log.info(
                    "recover_cluster_after_stop.waiting_for_worker_state",
                    cluster=cluster.name,
                    ready_workers=len(ready_workers),
                    expected_total=expected_total,
                )
                time.sleep(poll_interval_s)
                continue

            log.info(
                "recover_cluster_after_stop.done",
                cluster=cluster.name,
                ready_pods=len(live_ready_pods),
                ready_workers=len(ready_workers),
                expected_total=expected_total,
            )
            return

        except Exception as e:
            log.warning(
                "recover_cluster_after_stop.poll_failed",
                cluster=cluster.name,
                error=str(e),
            )

        time.sleep(poll_interval_s)

    raise TimeoutError(
        f"{cluster.name} did not recover after stop within {timeout_s}s"
    )