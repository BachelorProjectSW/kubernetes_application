import structlog
from ...models.basemodels import ClusterInformation, WorkerNode
from .client_setup import get_api_client

log = structlog.get_logger()


class ConfigStore:
    """Store for the current cluster config."""
    
    def __init__(self):
        """init config to none."""
        self.config: ClusterInformation | None = None

    def set(self, config: ClusterInformation):
        """Set the current config."""
        self.config = config

    def get(self):
        """Get the current config."""
        return self.config
    
    def refresh_config(self):
        """Fetch the current config from util."""
        self.config = config_store.get()
        if self.config is None:
            raise ValueError("No cluster config set in store")
        self.config.worker_nodes = None  

    def build_worker_nodes(self):
        """Build worker nodes using Kubernetes API or config defaults."""
        if self.config is None:
            self.refresh_config()

        if self.config.worker_nodes is not None:
            return self.config.worker_nodes

        api_client = get_api_client()
        nodes = api_client.list_node()
        worker_nodes = []

        for i, node in enumerate(nodes.items):
            labels = node.metadata.labels or {}
            # skip control plane nodes
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
                        status = "on" if condition.status == "True" else "off"
                        break

            worker_node = WorkerNode(
                name=name,
                ip=ip,
                status=status,
                gpio=0 #will later be assigned  
            )
            worker_nodes.append(worker_node)

        self.config.worker_nodes = worker_nodes
        self.assign_gpios()
        return self.config.worker_nodes

    def assign_gpios(self):
        """Assign GPIOs from config to each worker node."""
        if self.config.worker_nodes is None:
            self.build_worker_nodes()

        gpios = self.config.cluster_config.gpio_list
        if len(gpios) != len(self.config.worker_nodes):
            raise ValueError(
                f"Worker nodes and GPIOs count mismatch: "
                f"nodes={len(self.config.worker_nodes)} gpios={len(gpios)}"
            )

        for node, gpio in zip(self.config.worker_nodes, gpios):
            node.gpio = gpio
            log.debug("node.gpio_assigned", node=node)


    def get_worker_nodes_dict(self):
            """Return worker nodes only, as list of dicts."""
            if self.config.worker_nodes is None:
                self.build_worker_nodes()
            return [node.dict() for node in self.config.worker_nodes]

config_store = ConfigStore()