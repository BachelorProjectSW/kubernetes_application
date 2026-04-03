import requests
from ..util.all_configuration import config_store


def get_all_worker_nodes():
    """Return all working nodes for each cluster."""
    worker_nodes = []
    clusters = config_store.get_clusters()
    print(len(clusters))
    print("GNGA")
    for cluster in clusters:
        url = f"http://{cluster.ip}:{cluster.port}/get_cluster_working_nodes"
        print("url:", url)
        response = requests.get(url, timeout=5)
        print("reponse", response)
        worker_nodes.extend(response.json())

    return worker_nodes
