import structlog
from ...models.basemodels import ClusterInformation, WorkerNode
from .client_setup import get_api_client
import requests

log = structlog.get_logger()


class ConfigStore:
    """Store for the current cluster config."""

    def __init__(self):
        """Init config to none."""
        self.config: ClusterInformation | None = None

    def set(self, config: ClusterInformation):
        """Set the current config."""
        self.config = config

    def get(self):
        """Get the current config."""
        return self.config

    def build_worker_nodes(self):
        """Build worker nodes using Kubernetes API or config defaults."""
        if self.config is None:
            raise Exception("Config is not set yet")

        self.config.worker_nodes = []

        api_client = get_api_client()
        nodes = api_client.list_node()

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
                        status = "idle" if condition.status == "True" else "off"
                        break
            worker_node = WorkerNode(
                name=name,
                ip=ip,
                status=status,
                gpio=0,  # will later be assigned
                llama_nodeport=0   # Will be assigned later, based on k3d or k3s
            )
            self.config.worker_nodes.append(worker_node)

        self.assign_gpios()
        self.populate_service_ports()
        self.populate_worker_capacities()
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
        return [node.model_dump() for node in self.config.worker_nodes]

    def populate_service_ports(self):
        """Fetch NodePort from llama-service and save it in cluster config."""
        if self.config is None:
            raise Exception("Config is not set yet")

        api_client = get_api_client()
        service = api_client.read_namespaced_service(
            name="llama-service",
            namespace="default",
        )

        for port in service.spec.ports:
            if port.port == 8080:
                if port.node_port is None:
                    raise ValueError("llama-service has no nodePort")

                self.config.cluster_config.llama_nodeport = port.node_port
                log.debug(
                    "service.nodeport_discovered",
                    service_name="llama-service",
                    service_port=port.port,
                    node_port=port.node_port,
                )
                return

        raise ValueError("Could not find service port 8080 on llama-service")

    def populate_worker_capacities(self):
        """Fetch max_slots from each worker's llama server."""
        if self.config is None:
            raise Exception("Config is not set yet")

        if not self.config.worker_nodes:
            self.build_worker_nodes()
            return

        for worker in self.config.worker_nodes:
            if not worker.ip:
                worker.max_slots = 0
                worker.status = "off"
                continue

            try:
                if self.config.cluster_config.use_port_forward:
                    url = f"http://localhost:{self.config.cluster_config.llama_service_port}/props"
                else:
                    url = f"http://{worker.ip}:{self.config.cluster_config.llama_nodeport}/props"

                log.debug(
                    "cluster.worker_props_request",
                    worker_name=worker.name,
                    worker_ip=worker.ip,
                    url=url,
                )

                response = requests.get(url, timeout=10)
                response.raise_for_status()

                props = response.json()

                log.debug(
                    "cluster.worker_props_response",
                    worker_name=worker.name,
                    worker_ip=worker.ip,
                    props=props,
                )

                worker.max_slots = props.get("total_slots", 0)
                worker.status = "idle" if worker.max_slots > 0 else "off"

            except Exception as e:
                log.debug(
                    "cluster.worker_populate_capacity_failed",
                    worker_name=worker.name,
                    worker_ip=worker.ip,
                    error=str(e),
                )
                worker.max_slots = 0
                worker.status = "off"


config_store = ConfigStore()
