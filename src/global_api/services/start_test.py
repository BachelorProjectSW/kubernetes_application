from ...models.basemodels import Config, ClusterInformation
from ..util.all_configuration import config_store
import requests
from .power_scheduler import power_scheduler_loop
import asyncio
import threading


_power_scheduler_thread: threading.Thread | None = None


def _run_power_scheduler_loop():
    """Run the async power scheduler in a dedicated thread."""
    asyncio.run(power_scheduler_loop())


def start_test(config: Config):
    """Start the test and send configs."""
    try:
        global _power_scheduler_thread
        config_store.set(config)
        # TODO set start_time_real = current time datetime.now().strf()
        for cluster in config.clusters:

            cluster_information = ClusterInformation(
                cluster_config=cluster,
                question_config=config.question,
                worker_nodes=[]
            )
            ip = cluster.ip
            port = cluster.port
            url = f"http://{ip}:{port}/set_config"

            response = requests.post(url, json=cluster_information.model_dump())
            response.raise_for_status()

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
        name = config.name
        return f"{name} test are running succesfully"
    except Exception as e:
        raise Exception(f"test failed: {e}")


def stop_test():
    """Stop the test."""
    config_store.stop_power_scheduler()
    # TODO code for shutdown on worker_nodes and return logs
    logs = "logs"
    return logs
