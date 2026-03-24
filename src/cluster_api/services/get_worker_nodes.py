from ..util.client_setup import get_api_client
import structlog

log = structlog.get_logger()


def get_cluster_nodes():
    """Return a JSON object with all the active working nodes."""
    api_client = get_api_client()
    nodes = api_client.list_node()
    worker_nodes = []
    for node in nodes.items:
        # Skip control plane
        labels = str(node.metadata.labels) or ""  # Empty if not exist instead of crash
        if "'node-role.kubernetes.io/control-plane': 'true'" in labels:
            log.debug("node.skipped", name=node.metadata.name, reason="control-plane")
            continue

        name = node.metadata.name

        worker_nodes.append({
            "name": name
            })

    node_names = [n["name"] for n in worker_nodes]
    log.info("worker_nodes.found", count=len(worker_nodes), nodes=node_names)

    return worker_nodes
