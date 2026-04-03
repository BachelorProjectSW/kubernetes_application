import structlog
from ...models.basemodels import ClusterInformation
from ..util.cluster_config import config_store

log = structlog.get_logger()


class WorkerNode:
    """Information about a worker node."""

    def __init__(self, name: str, ip: str, status: str):
        self.name = name
        self.ip = ip
        self.status = status
        self.gpio = 0
        self.logs = ""

    def __repr__(self):
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
    """Single cluster using its own ClusterInformation from config_store."""

    def __init__(self):
        self.config: ClusterInformation | None = config_store.get()
        if self.config is None:
            raise ValueError("No cluster config found in config_store")

        # Build worker nodes and assign GPIOs
        self.nodes = self._build_nodes()
        self._assign_gpios()

    def _build_nodes(self):
        """Create WorkerNode instances based on GPIO list count."""
        gpio_count = len(self.config.cluster_config.gpio_list)
        nodes = []
        for i in range(gpio_count):
            # Node name and IP are placeholders, can be updated later
            node = WorkerNode(
                name=f"{self.config.cluster_config.name}-node-{i+1}",
                ip=f"{self.config.cluster_config.ip[:-1]}{100+i}",  # basic IP assignment
                status="active",
            )
            nodes.append(node)
        return nodes

    def _assign_gpios(self):
        """Assign GPIOs from config to worker nodes."""
        gpios = self.config.cluster_config.gpio_list
        if len(gpios) != len(self.nodes):
            raise ValueError(
                f"Worker nodes and GPIOs count mismatch: "
                f"nodes={len(self.nodes)} gpios={len(gpios)}"
            )
        for node, gpio in zip(self.nodes, gpios):
            node.gpio = gpio
            log.debug("node.gpio_assigned", node=node)

    def refresh_nodes(self):
        """Rebuild nodes if config changed."""
        self.config = config_store.get()
        if self.config is None:
            raise ValueError("No cluster config found in config_store")
        self.nodes = self._build_nodes()
        self._assign_gpios()

    def to_dict(self):
        """Return nodes as list of dictionaries."""
        return [node.to_dict() for node in self.nodes]