import requests
from ..util.cluster_connection import get_all_clusters_config


def get_all_worker_nodes():
    """Return all working nodes for each cluster."""
    worker_nodes = []
    for cluster, config in get_all_clusters_config().items():
        url = f"http://{config["ip"]:{config["port"]}}/get_cluster_nodes"
        response = requests.get(url, timeout=5)
        worker_nodes.extend(response.json())

    return worker_nodes

