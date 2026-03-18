from cluster_api.util.client_setup import get_api_clients


def get_cluster_nodes(api_client):
    """Return a JSON object with all the active working nodes."""
    nodes = api_client.list_node()
    worker_nodes = []
    for node in nodes.items:
        # Skip control plane
        labels = str(node.metadata.labels) or ""  # Empty if not exist instead of crash
        if "'node-role.kubernetes.io/control-plane': 'true'" in labels:
            continue

        name = node.metadata.name

        worker_nodes.append({
            "name": name
        })

    return worker_nodes


def get_all_nodes():
    """Return a list with JSON object of all active working nodes from each cluster."""
    api_clients = get_api_clients()
    total_worker_nodes = []
    for api_client in api_clients:
        worker_nodes = get_cluster_nodes(api_client)
        total_worker_nodes.extend(worker_nodes)

    return total_worker_nodes
