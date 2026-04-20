from ...models.basemodels import Config, ClusterInformation
from ..util.all_configuration import config_store
from ...custom_logging.logger import set_current_config_id
import requests
import structlog
from .power_scheduler import power_scheduler_loop
import asyncio
import threading


_power_scheduler_thread: threading.Thread | None = None
log = structlog.get_logger()


def _run_power_scheduler_loop():
    """Run the async power scheduler in a dedicated thread."""
    asyncio.run(power_scheduler_loop())

def ensure_nodes_ready(cluster):
    """Turn on all nodes in the cluster before starting the test."""
    base = f"http://{cluster.ip}:{cluster.port}"

    try:
        info = requests.get(f"{base}/get_cluster_information", timeout=10).json()
    except Exception as e:
        log.warning("global.start_test.cluster_info_failed", cluster=cluster.name, error=str(e))
        return

    nodes = info.get("worker_nodes", [])
    total = len(nodes)

    log.info("global.start_test.turning_on_all_nodes", cluster=cluster.name, total=total)

    try:
        response = requests.post(
            f"{base}/turn_on_nodes/",
            params={"number_of_nodes": total},
            timeout=180,
        )
        response.raise_for_status()
        log.info("global.start_test.turn_on_requested", cluster=cluster.name, requested=total)
    except Exception as e:
        log.warning("global.start_test.turn_on_failed", cluster=cluster.name, error=str(e))

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
            ensure_nodes_ready(cluster)
            log.info(
                "global.start_test.set_config.done",
                cluster=cluster.name,
                status_code=response.status_code,
            )

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
    config_store.stop_power_scheduler()
    # TODO code for shutdown on worker_nodes and return logs
    logs = "logs"
    return logs
