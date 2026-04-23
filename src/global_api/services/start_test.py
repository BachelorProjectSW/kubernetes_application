from ...models.basemodels import Config, ClusterInformation
from ..util.all_configuration import config_store
from ...custom_logging.logger import set_current_config_id
import requests
import structlog
from .power_scheduler import power_scheduler_loop
import asyncio
import threading
from .ensure_nodes_ready import ensure_nodes_ready
from datetime import datetime, timezone


_power_scheduler_thread: threading.Thread | None = None
log = structlog.get_logger()


def _run_power_scheduler_loop():
    """Run the async power scheduler in a dedicated thread."""
    asyncio.run(power_scheduler_loop())


def start_test(config: Config):
    """Start the test and send configs."""
    try:
        global _power_scheduler_thread
        config.start.start_time_real = datetime.now(timezone.utc).isoformat()
        set_current_config_id(config.id)
        config_store.set(config)
        log.info("global_api.test.start_requested", config_id=config.id, test_name=config.name)

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
            #TODO VIRKER IKKE NÅR WORKER NODES ER SLUKKET TIL AT STARTE MED:D pga timeout
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
        log.exception("global_api.test.start_failed", error=str(e))
        raise Exception(f"test failed: {e}")


def stop_test():
    """Stop the test."""
    config = config_store.get()
    config_store.stop_power_scheduler()
    if config:
        for cluster in config.clusters:
            try:
                # All pods are deleted (recreated automatically).
                # Because when the test is stopped --> possibility of inflight-requests
                # These needs to be deleted, such that the next test can run deterministcally
                requests.post(
                    f"http://{cluster.ip}:{cluster.port}/cancel_all_llama_pods",
                    timeout=60
                )
                log.info("global.stop_test.pods_deleted", cluster=cluster.name)
            except Exception as e:
                log.warning("global.stop_test.pods_delete_failed", cluster=cluster.name, error=str(e))
    log.info("global.stop_test.done")
    return {"message": "Test stopped"}
