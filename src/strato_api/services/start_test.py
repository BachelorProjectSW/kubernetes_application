import requests
from ...models.basemodels import *
from test.k3d.cluster_configs.test_config import get_test_config
def start_test(config: Config):
    """Start test to the global scheduler. Further this should run chron job ensure the next in queue begins"""
    ip = config.global_scheduler.ip
    port = config.global_scheduler.port
    url = f"http://{ip}:{port}/start_test" #url should be to global scheduler

    response = requests.post(url, json=config.model_dump())

    return response.json()


def start_test_test():
    """Start test test"""
    
    return start_test(get_test_config())