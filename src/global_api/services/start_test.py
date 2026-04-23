import time

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


_power_scheduler_thread: threading.Thread | None = None
log = structlog.get_logger()


def _run_power_scheduler_loop():
    """Run the async power scheduler in a dedicated thread."""
    asyncio.run(power_scheduler_loop())


def start_test(config: Config):
    """Start the test and send configs."""
    try:
        global _power_scheduler_thread
        set_current_config_id(config.id)
        config_store.set(config)
        test_state.start()
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
        log.info("global_api.test.start_completed", config_id=config.id, test_name=name)
        return f"{name} test are running succesfully"
    except Exception as e:
        test_state.reset()
        log.exception("global_api.test.start_failed", error=str(e))
        raise Exception(f"test failed: {e}")


# def stop_test():
#     """Stop the test."""
#     config = config_store.get()
#     config_store.stop_power_scheduler()
#     if config:
#         for cluster in config.clusters:
#             try:
#                 # All pods are deleted (recreated automatically).
#                 # Because when the test is stopped --> possibility of inflight-requests
#                 # These needs to be deleted, such that the next test can run deterministcally
#                 requests.post(
#                     f"http://{cluster.ip}:{cluster.port}/cancel_all_llama_pods",
#                     timeout=60
#                 )
#                 log.info("global.stop_test.pods_deleted", cluster=cluster.name)
#             except Exception as e:
#                 log.warning("global.stop_test.pods_delete_failed", cluster=cluster.name, error=str(e))
    
#     threading.Thread(target=stop_global_pod, daemon=True).start()
#     log.info("global.stop_test.done")
#     return {"message": "Test stopped"}

def _recover_clusters_after_stop(clusters):
    all_ok = True

    for cluster in clusters:
        try:
            ensure_nodes_ready(cluster, timeout_s=400)
            log.info("global.stop_test.cluster_ready_again", cluster=cluster.name)
        except Exception as e:
            all_ok = False
            log.warning(
                "global.stop_test.cluster_recovery_failed",
                cluster=cluster.name,
                error=str(e),
            )

    test_state.reset()
    log.info("global.stop_test.recovery_finished", success=all_ok)


def stop_test():
    config = config_store.get()
    test_state.mark_stopping()
    config_store.stop_power_scheduler()

    if config:
        for cluster in config.clusters:
            stop_cluster(cluster)

        for cluster in config.clusters:
            cancel_cluster_pods(cluster)

        threading.Thread(
            target=_recover_clusters_after_stop,
            args=(config.clusters,),
            daemon=True,
        ).start()

    log.info("global.stop_test.done")
    return {"message": "Stop requested"}

def cancel_cluster_pods(cluster):
    try:
        response = requests.post(
            f"http://{cluster.ip}:{cluster.port}/cancel_all_llama_pods",
            timeout=30,
        )
        response.raise_for_status()
        log.info(
            "global.stop_test.cluster_cancel_requested",
            cluster=cluster.name,
            status_code=response.status_code,
        )
    except Exception as e:
        log.warning(
            "global.stop_test.cluster_cancel_failed",
            cluster=cluster.name,
            error=str(e),
        )

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