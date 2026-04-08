import requests
from ..util.all_configuration import config_store


def get_all_worker_nodes():
    """Return all working nodes for each cluster."""
    worker_nodes = []
    clusters = config_store.get_clusters()
    for cluster in clusters:
        url = f"http://{cluster.ip}:{cluster.port}/get_cluster_working_nodes"
        response = requests.get(url, json="", timeout=5)
        worker_nodes.extend(response.json())

    return worker_nodes
