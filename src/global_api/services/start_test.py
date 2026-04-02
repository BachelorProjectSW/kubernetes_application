from ...models.basemodels import Config, ClusterInformation
from ..util.all_configuration import config_store
import requests

def start_test(config: Config):
    """Start the test and send configs"""
    config_store.set(config)
    for cluster in config.clusters:

        cluster_information = ClusterInformation(
            cluster_config=cluster,
            question_config=config.question
        )
        ip = cluster.ip
        port = cluster.port
        url = f"http://{ip}:{port}/set_config" 

        response = requests.post(url, json=cluster_information.model_dump())
        print(response)
        #TODO handle response

        #TODO boot up all clusters


    #TODO send configuration to cluster API (waits for its to be applied correctly)
    name = config.name
    return f"{name} test are running succesfully"


def stop_test():
    """Stop the test."""
    #code for shutdown on clusters and return logs
    logs = "logs"
    return logs