import structlog
from ...models.basemodels import ClusterInformation, WorkerNode
from ...models.enum import WorkerStatus
from .client_setup import get_api_client
import requests

log = structlog.get_logger()


class ConfigStore:
    """In-memory holder and helper for the active cluster configuration.

    This class stores the currently active `ClusterInformation` and provides
    convenience methods to build `WorkerNode` objects from a live Kubernetes
    cluster (or from test fixtures), assign GPIO pins and forwarded ports, and
    read runtime information such as Llama hostPorts and per-worker capacities.

    """

    def __init__(self):
        """Init config to none."""
        self.config: ClusterInformation | None = None

    def set(self, config: ClusterInformation):
        """Store a `ClusterInformation` object to be used by helper methods.

        Args:
            config: The `ClusterInformation` instance to store.

        """
        self.config = config

    def get(self):
        """Return the currently stored `ClusterInformation`.

        Returns:
            The stored `ClusterInformation` instance, or ``None`` when no
            configuration has been loaded yet.

        """
        return self.config

    def build_worker_nodes(self):
        """Discover cluster worker nodes and populate `config.worker_nodes`.

        This queries the Kubernetes API for nodes, skips control-plane nodes,
        extracts an IP address and ready state for each worker node, and
        produces a list of `WorkerNode` objects attached to the stored
        `ClusterInformation`.

        Returns:
            The list of created `WorkerNode` objects.

        Raises:
            Exception: If no configuration has been `set()` prior to calling
                this method.

        """
        if self.config is None:
            raise Exception("Config is not set yet")

        self.config.worker_nodes = []

        api_client = get_api_client()
        nodes = api_client.list_node()

        for i, node in enumerate(nodes.items):
            labels = node.metadata.labels or {}
            # skip control plane nodes
            if labels.get("node-role.kubernetes.io/control-plane") == "true":
                log.debug(
                    "cluster_api.config.control_plane_node_skipped",
                    cluster_name=self.config.cluster_config.name,
                    worker_node=node.metadata.name,
                    reason="control-plane",
                )
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

            status = WorkerStatus.OFF
            if getattr(node.status, "conditions", None):
                for condition in node.status.conditions:
                    if condition.type == "Ready":
                        status = WorkerStatus.IDLE if condition.status == "True" else WorkerStatus.OFF
                        break
            worker_node = WorkerNode(
                name=name,
                ip=ip,
                status=status,
                gpio=0,  # will later be assigned
            )
            self.config.worker_nodes.append(worker_node)

        self.assign_gpios()
        if self.config.cluster_config.k3d:
            self.assign_forwarded_ports()
        else:
            self.populate_host_port()
        self.populate_worker_capacities()
        return self.config.worker_nodes

    def assign_gpios(self):
        """Assign GPIO numbers from the cluster config to each worker node.

        The cluster configuration includes a `gpio_list` which defines one GPIO
        pin per worker. This method writes the GPIO number into each
        `WorkerNode.gpio` field in the same order as the workers list. The
        method raises a ``ValueError`` when the number of GPIOs does not match
        the number of discovered worker nodes.
        """
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
            log.debug(
                "cluster_api.config.worker_gpio_assigned",
                cluster_name=self.config.cluster_config.name,
                worker_node=node.name,
                gpio=node.gpio,
            )

    def get_worker_nodes_dict(self):
        """Return the list of worker nodes as plain dictionaries.

        This is convenient for HTTP responses where the API should return a
        JSON-serializable structure rather than Pydantic models.

        Returns:
            A list of dicts, one per worker node. If `worker_nodes` is not yet
            populated the method will discover nodes by calling
            `build_worker_nodes()`.

        """
        if self.config.worker_nodes is None:
            self.build_worker_nodes()
        return [node.model_dump() for node in self.config.worker_nodes]

    def assign_forwarded_ports(self):
        """Assign local forwarded ports to workers when running in `k3d` mode.

        Many tests and local deployments use `kubectl port-forward` so each
        worker pod is reachable on `localhost:<forwarded_port>`. This method
        assigns a stable forwarded port to each worker based on the cluster's
        configured `llama_service_port` and the worker's sorted name order.
        """
        if self.config is None:
            raise Exception("Config is not set yet")

        base_port = int(self.config.cluster_config.llama_service_port)

        workers = sorted(self.config.worker_nodes, key=lambda worker: worker.name)  # Sort by name

        for index, worker in enumerate(workers):
            worker.forwarded_port = base_port + index
            log.debug(
                "cluster_api.config.worker_forwarded_port_assigned",
                cluster_name=self.config.cluster_config.name,
                worker_node=worker.name,
                worker_ip=worker.ip,
                forwarded_port=worker.forwarded_port,
            )

    def populate_host_port(self):
        """Discover the Llama service `hostPort` from running pods.

        This inspects running, ready pods labeled `app=llama-server` and reads
        container `hostPort` fields. If a single consistent hostPort is found
        it is stored in `config.cluster_config.llama_hostport`. If multiple
        inconsistent hostPorts are discovered the method raises ``ValueError``.
        If no ready pod exposes a hostPort the existing configuration value is
        left untouched and a warning is logged.
        """
        if self.config is None:
            raise Exception("Config is not set yet")

        api_client = get_api_client()

        pods = api_client.list_namespaced_pod(
            namespace="default",
            label_selector="app=llama-server",
        ).items

        found_ports = set()

        for pod in pods:
            if getattr(pod.status, "phase", None) != "Running":  # only choose pods that are running
                continue

            # only pods that are ready
            conditions = getattr(pod.status, "conditions", None) or []
            pod_ready = any(c.type == "Ready" and c.status == "True" for c in conditions)
            if not pod_ready:
                continue

            containers = getattr(pod.spec, "containers", None) or []
            for container in containers:
                if container.name != "llama":
                    continue

                for port in container.ports or []:
                    if port.host_port is not None:
                        found_ports.add(port.host_port)

        if not found_ports:
            log.warning(
                "cluster_api.config.llama_hostport_not_found",
                cluster_name=self.config.cluster_config.name,
                worker_node=None,
                reason="no_running_ready_llama_pod_with_hostport",
                fallback_llama_hostport=self.config.cluster_config.llama_hostport,
            )
            return

        if len(found_ports) > 1:
            raise ValueError(f"Inconsistent llama hostPorts found: {sorted(found_ports)}")

        self.config.cluster_config.llama_hostport = found_ports.pop()  # Returns the removed value

        log.debug(
            "cluster_api.config.llama_hostport_discovered",
            cluster_name=self.config.cluster_config.name,
            worker_node=None,
            llama_hostport=self.config.cluster_config.llama_hostport,
        )

    def populate_worker_capacities(self):
        """Probe each worker's Llama `/props` endpoint to determine capacity.

        For each worker this method builds a request URL (localhost forwarded
        port when `k3d` is enabled, otherwise the discovered host port), calls
        the `/props` endpoint, and sets `worker.max_slots` from the returned
        JSON's `total_slots` value. When running in `k3d` mode the probe will
        fall back to a safe default capacity (1) if the HTTP request fails,
        because pods may still be starting during test bootstrapping.
        """
        if self.config is None:
            raise Exception("Config is not set yet")

        if not self.config.worker_nodes:
            return

        for worker in self.config.worker_nodes:
            if not worker.ip:
                worker.max_slots = 0
                worker.status = WorkerStatus.OFF
                continue

            try:
                if self.config.cluster_config.k3d:
                    url = f"http://localhost:{worker.forwarded_port}/props"
                else:
                    url = f"http://{worker.ip}:{self.config.cluster_config.llama_hostport}/props"

                log.debug(
                    "cluster_api.config.worker_props_request_started",
                    cluster_name=self.config.cluster_config.name,
                    worker_node=worker.name,
                    worker_ip=worker.ip,
                    url=url,
                )

                response = requests.get(url, timeout=120)
                response.raise_for_status()

                props = response.json()

                log.debug(
                    "cluster_api.config.worker_props_request_succeeded",
                    cluster_name=self.config.cluster_config.name,
                    worker_node=worker.name,
                    worker_ip=worker.ip,
                    props=props,
                )

                worker.max_slots = props.get("total_slots", 0)
                worker.status = WorkerStatus.IDLE if worker.max_slots > 0 else WorkerStatus.OFF

            except Exception as e:
                log.warning(
                    "cluster_api.config.worker_capacity_probe_failed",
                    cluster_name=self.config.cluster_config.name,
                    worker_node=worker.name,
                    worker_ip=worker.ip,
                    url=url,
                    error=str(e),
                )
                # In k3d mode, use default capacity when probe fails (pods may be starting)
                if self.config.cluster_config.k3d:
                    worker.max_slots = 1  # Default capacity for k3d testing
                    worker.status = WorkerStatus.IDLE
                    log.debug(
                        "cluster_api.config.worker_capacity_probe_k3d_fallback",
                        cluster_name=self.config.cluster_config.name,
                        worker_node=worker.name,
                        max_slots=worker.max_slots,
                    )
                else:
                    worker.max_slots = 0
                    worker.status = WorkerStatus.OFF


config_store = ConfigStore()
