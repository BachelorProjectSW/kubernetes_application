from ...models.basemodels import Config, ClusterInformation
from ..util.all_configuration import config_store
from datetime import datetime
import requests


def start_test(config: Config):
    """Start the test and send configs."""
    try:
        config_store.set(config)
        config_store.set_current_time()
        print(config_store.start.start_time_real)
        #TODO get cost and energy from API and store it somewhere.
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
        name = config.name
        return f"{name} test are running succesfully"
    except Exception as e:
        raise Exception(f"test failed: {e}")


def stop_test():
    """Stop the test."""
    # TODO code for shutdown on worker_nodes and return logs
    logs = "logs"
    return logs
