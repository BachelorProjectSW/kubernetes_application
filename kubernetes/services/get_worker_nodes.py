from util.client_setup import get_api_client


def get_worker_nodes():
    """Return a JSON object with all the active working nodes."""
    api_client = get_api_client()
    nodes = api_client.list_node()
    worker_nodes = []
    for node in nodes.items:
        # Skip control plane
        labels = str(node.metadata.labels) or ""  # Empty if not exist instead of crash
        if "'node-role.kubernetes.io/control-plane': 'true'" in labels:
            continue

        name = node.metadata.name
        active_node = False
        for condition in node.status.conditions:
            if condition.type == "Ready" and condition.status == "True":
                active_node = True

        if active_node:
            worker_nodes.append({
            "name": name
            })

    return worker_nodes
