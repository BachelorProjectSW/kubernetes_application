import time

from .validate_config import validate_config
from ...models.basemodels import Config, ClusterInformation
from ..util.all_configuration import config_store
from ...custom_logging.logger import set_current_config_id
import requests
import structlog
from .power_scheduler import power_scheduler_loop
import asyncio
import threading
from .ensure_nodes_ready import ensure_nodes_ready


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
        log.info("global.start_test.begin", config_id=config.id, test_name=config.name)
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

            log.info("global.start_test.set_config.start", cluster=cluster.name, url=url)
            response = requests.post(url, json=cluster_information.model_dump(), timeout=30)
            response.raise_for_status()
            log.info(
                "global.start_test.set_config.done",
                cluster=cluster.name,
                status_code=response.status_code,
            )
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
                log.info("global.start_test.power_scheduler.started")
        name = config.name
        log.info("global.start_test.done", config_id=config.id, test_name=name)
        return f"{name} test are running succesfully"
    except Exception as e:
        log.exception("global.start_test.failed", error=str(e))
        raise Exception(f"test failed: {e}")

def stop_test():
    """Stop the test."""
    config = config_store.get()
    config_store.stop_power_scheduler()
    if config:
        for cluster in config.clusters:
            try:
                requests.post(
                    f"http://{cluster.ip}:{cluster.port}/cancel_all_llama_pods",
                    timeout=60
                )
                log.info("global.stop_test.pods_deleted", cluster=cluster.name)
            except Exception as e:
                log.warning("global.stop_test.pods_delete_failed", 
                           cluster=cluster.name, error=str(e))
    log.info("global.stop_test.done")
    return {"message": "Test stopped"}
