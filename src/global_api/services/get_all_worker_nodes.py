import requests
import structlog
from ..util.all_configuration import config_store


log = structlog.get_logger()


def get_all_worker_nodes():
    """Return all working nodes for each cluster."""
    worker_nodes = []
    config = config_store.get()
    if config is None:
        log.warning("global.get_all_worker_nodes.no_config")
        return worker_nodes

    clusters = config_store.get_clusters()
    for cluster in clusters:
        url = f"http://{cluster.ip}:{cluster.port}/get_cluster_working_nodes"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                worker_nodes.extend(payload)
                log.info(
                    "global.get_all_worker_nodes.cluster_ok",
                    cluster=cluster.name,
                    url=url,
                    worker_count=len(payload),
                )
            else:
                log.warning(
                    "global.get_all_worker_nodes.invalid_payload",
                    cluster=cluster.name,
                    url=url,
                    payload_type=type(payload).__name__,
                )
        except requests.RequestException as e:
            log.warning(
                "global.get_all_worker_nodes.cluster_unreachable",
                cluster=cluster.name,
                url=url,
                error=str(e),
            )

    log.info("global.get_all_worker_nodes.done", total_workers=len(worker_nodes))
    return worker_nodes
