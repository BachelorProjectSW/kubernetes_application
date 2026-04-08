from ...models.basemodels import Config, ClusterInformation
from ..util.all_configuration import config_store
import requests


def start_test(config: Config):
    """Start the test and send configs."""
    try:
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

        # TODO setup powershcheduler (remeber to use basemodel PowerSchedulerConfig)
        name = config.name
        return f"{name} test are running succesfully"
    except Exception as e:
        raise Exception(f"test failed: {e}")


def stop_test():
    """Stop the test."""
    # TODO code for shutdown on worker_nodes and return logs
    logs = "logs"
    return logs
