import structlog

from ...global_api.util.cluster_connection import get_all_clusters_config
from ..util.client_setup import get_api_client

log = structlog.get_logger()
_CLUSTERS: dict[str, "Cluster"] = {}


class WorkerNode:
    """All information of a worker node"""

    def __init__(self, name, ip, status):
        self.name = name
        self.ip = ip
        self.status = status
        self.gpio = 0
        self.logs = ""

    def __repr__(self):
        """Use this to print all self using print()."""
        return f"{self.__class__.__name__}({self.__dict__})"

    def to_dict(self):
        return {
            "name": self.name,
            "ip": self.ip,
            "status": self.status,
            "gpio": self.gpio,
            "logs": self.logs,
        }


class Cluster:
    def __init__(self, name):
        self.name = name
        self.nodes = self.get_cluster_working_nodes()
        self.assign_gpios()

    def refresh_nodes(self):
        self.nodes = self.get_cluster_working_nodes()
        self.assign_gpios()
        return self.nodes

    def to_dict(self):
        return [node.to_dict() for node in self.nodes]

    def assign_gpios(self):
        all_worker_nodes = self.nodes
        gpios = get_all_clusters_config()[self.name]["gpio"]

        worker_len = len(all_worker_nodes)
        gpios_len = len(gpios)
        if gpios_len != worker_len:
            raise ValueError(
                f"""Worker nodes and assigned gpios is not the same 
                nodes={worker_len} gpios={gpios_len}"""
            )
        for i in range(worker_len):
            all_worker_nodes[i].gpio = gpios[i]
            print(all_worker_nodes[i])

    def get_cluster_working_nodes(self):
        """Return a JSON object with all the active working nodes."""
        api_client = get_api_client()
        nodes = api_client.list_node()
        worker_nodes = []
        for node in nodes.items:
            # Skip control plane
            labels = node.metadata.labels or {}
            if labels.get("node-role.kubernetes.io/control-plane") == "true":
                log.debug("node.skipped", name=node.metadata.name, reason="control-plane")
                continue

            name = node.metadata.name
            ip = ""
            if getattr(node.status, "addresses", None):
                for address in node.status.addresses:
                    if address.type == "InternalIP":
                        ip = address.address
                        break
                if not ip:
                    ip = node.status.addresses[0].address

            status = "unknown"
            if getattr(node.status, "conditions", None):
                for condition in node.status.conditions:
                    if condition.type == "Ready":
                        status = "active" if condition.status == "True" else "inactive"
                        break

            worker_nodes.append(
                WorkerNode(name, ip, status, )
            )

        return worker_nodes


def get_cluster_working_nodes(cluster_name="dk"):
    """Compatibility wrapper used by routes."""
    cluster = get_cluster(cluster_name, refresh=True)
    return cluster.to_dict()


def get_cluster(cluster_name, refresh=False):
    """Return a cached Cluster instance for this process."""
    cluster = _CLUSTERS.get(cluster_name)
    if cluster is None:
        cluster = Cluster(cluster_name)
        _CLUSTERS[cluster_name] = cluster
    elif refresh:
        cluster.refresh_nodes()

    return cluster.to_dict()
