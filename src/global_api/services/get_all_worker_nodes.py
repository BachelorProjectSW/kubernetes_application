from ..util.cluster_connection import get_all_clusters_ip


def get_all_worker_nodes():
    """Return all working nodes for each cluster."""
    for cluster, ip in get_all_clusters_ip().items():
        print(cluster, ip)

    return [{"name": "jetson1"}]
