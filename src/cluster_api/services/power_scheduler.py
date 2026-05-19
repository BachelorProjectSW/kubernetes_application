import paramiko
import structlog
from concurrent.futures import ThreadPoolExecutor
from ...models.basemodels import WorkerNode
from ..util.cluster_config import config_store
from ..util.client_setup import get_api_client
from ...models.enum import WorkerStatus
from ...custom_logging.util.log_reader import get_worker_nodes_logs
from datetime import datetime, timezone
import subprocess
import time
from ...custom_logging.logger import log_node_status_snapshot
import requests

log = structlog.get_logger()


def run_cmd(cmd):
    """Run a shell command and return its standard output.

    Args:
        cmd: Command string or list passed to ``subprocess.run``.

    Returns:
        The captured stdout as a string.

    """
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def turn_on_node(worker_node: WorkerNode, cluster_name: str):
    """Pulse the node's GPIO pin to power it on.

    Args:
        worker_node: Worker to power on.
        cluster_name: Name of the cluster the worker belongs to.

    Returns:
        ``True`` when the GPIO pulse was sent successfully, otherwise ``False``.

    """
    try:
        gpio = worker_node.gpio
        log.debug(
            "cluster_api.power.turn_on_gpio_pulse_started",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            gpio=gpio,
        )
        run_cmd(f"gpioset gpiochip4 {gpio}=1")
        time.sleep(0.5)
        run_cmd(f"gpioset gpiochip4 {gpio}=0")
        log.debug(
            "cluster_api.power.turn_on_gpio_pulse_completed",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            gpio=gpio,
        )
        worker_node.status = WorkerStatus.TURNING_ON
        log_node_status_snapshot(cluster_name, worker_node)
        return True
    except Exception as e:
        log.warning(
            "cluster_api.power.turn_on_failed",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            error=str(e),
        )
        return False


def turn_off_node(worker_node: WorkerNode, cluster_name: str):
    """Shut a worker down over SSH after checking it is safe to do so.

    Args:
        worker_node: Worker to power off.
        cluster_name: Name of the cluster the worker belongs to.

    Returns:
        ``True`` when the shutdown request was sent, otherwise ``False``.

    """
    try:
        log.info("cluster_api.power.turning_off_node", cluster=cluster_name, node=worker_node)
        worker_node.status = WorkerStatus.TURNING_OFF
        log_node_status_snapshot(cluster_name, worker_node)
        time.sleep(10)

        if worker_node.inflight_requests > 0:
            worker_node.status = WorkerStatus.IDLE
            log_node_status_snapshot(cluster_name, worker_node)
            log.warning(
                "cluster_api.power.turn_off_aborted_inflight_requests",
                cluster_name=cluster_name,
                worker_node=worker_node.name,
                inflight_requests=worker_node.inflight_requests,
            )
            return False

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(
            hostname=worker_node.ip,
            username=worker_node.name,
            password=worker_node.name
        )

        # -S makes sudo read password from stdin
        command = "sudo -S shutdown now"

        stdin, stdout, stderr = client.exec_command(command)

        # send password to sudo
        stdin.write(worker_node.name + "\n")
        stdin.flush()

        # read output
        out = stdout.read().decode()
        err = stderr.read().decode()

        log.debug(
            "cluster_api.power.turn_off_shutdown_output",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            stdout=out,
            stderr=err,
        )

        client.close()
        # Sleep 20 seconds to ensure its turned off.
        time.sleep(20)
        worker_node.status = WorkerStatus.OFF
        log_node_status_snapshot(cluster_name, worker_node)
        return True
    except Exception as e:
        worker_node.status = WorkerStatus.IDLE
        log_node_status_snapshot(cluster_name, worker_node)
        log.warning(
            "cluster_api.power.turn_off_failed",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            error=str(e),
        )
        return False


def check_if_llama_pod_is_ready(
    worker_node: WorkerNode,
    api_client,
    cluster_name: str,
    namespace: str = "default"
    ) -> bool:
    """Check whether the worker currently has a running and ready llama pod.

    Args:
        worker_node: Worker node to inspect.
        api_client: Kubernetes API client used to query pods.
        cluster_name: Name of the cluster the worker belongs to.
        namespace: Kubernetes namespace to inspect.

    Returns:
        ``True`` when at least one matching pod is running and ready, otherwise ``False``.

    """
    try:
        pods = api_client.list_namespaced_pod(
            namespace=namespace,
            field_selector=f"spec.nodeName={worker_node.name}",
            label_selector="app=llama-server",
        ).items

        for pod in pods:
            if getattr(pod.status, "phase", None) != "Running":
                continue

            conditions = getattr(pod.status, "conditions", None) or []
            # Is the pod ready, this uses readiness probe (so the container is also ready)
            pod_ready = any(c.type == "Ready" and c.status == "True" for c in conditions)

            if pod_ready:
                return True

        return False

    except Exception as e:
        log.warning(
            "cluster_api.power.pod_readiness_check_failed",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            error=str(e),
        )
        return False


def refresh_worker_capacity(worker_node: WorkerNode, cluster_config) -> bool:
    """Refresh a worker's slot capacity by calling its llama ``/props`` endpoint.

    Args:
        worker_node: Worker node to update.
        cluster_config: Cluster information used to build the request URL.

    Returns:
        ``True`` when capacity could be read and is greater than zero, otherwise ``False``.

    """
    try:
        if cluster_config.cluster_config.k3d:
            url = f"http://localhost:{worker_node.forwarded_port}/props"
        else:
            url = f"http://{worker_node.ip}:{cluster_config.cluster_config.llama_hostport}/props"

        log.debug(
            "cluster_api.power.worker_capacity_refresh_started",
            cluster_name=cluster_config.cluster_config.name,
            worker_node=worker_node.name,
            url=url,
        )

        response = requests.get(url, timeout=30)
        response.raise_for_status()
        props = response.json()

        # Sets the max_slot, by getting it from the max_slots dict, if no "total_slots" exists, set it to 0
        worker_node.max_slots = props.get("total_slots", 0)

        if worker_node.max_slots > 0:
            worker_node.status = WorkerStatus.IDLE
            log_node_status_snapshot(cluster_config.cluster_config.name, worker_node)
            return True

        log.warning(
            "cluster_api.power.worker_capacity_refresh_zero_slots",
            cluster_name=cluster_config.cluster_config.name,
            worker_node=worker_node.name,
            props=props,
        )
        return False

    except Exception as e:
        log.warning(
            "cluster_api.power.worker_capacity_refresh_failed",
            cluster_name=cluster_config.cluster_config.name,
            worker_node=worker_node.name,
            error=str(e),
        )
        return False


def wait_for_nodes_to_be_ready(
        worker_nodes: list[WorkerNode],
        cluster_name: str,
        timeout_s: int = 300,
        poll_interval_s: int = 2
        ) -> bool:
    """Wait until all selected nodes have a ready llama pod and valid capacity.

    Args:
        worker_nodes: Workers that should be confirmed ready.
        cluster_name: Name of the cluster these workers belong to.
        timeout_s: Maximum number of seconds to wait.
        poll_interval_s: Delay between readiness checks.

    Returns:
        ``True`` when every worker becomes ready before the timeout, otherwise ``False``.

    """
    deadline = time.time() + timeout_s
    api_client = get_api_client()
    cluster_config = config_store.get()

    while time.time() < deadline:
        ready_nodes = []

        for node in worker_nodes:
            pod_ready = check_if_llama_pod_is_ready(node, api_client, cluster_name)
            log.debug("cluster_api.pod.pod_ready", pod_ready=pod_ready, node=node.name)
            if not pod_ready:
                continue

            if node.max_slots > 0:
                ready_nodes.append(node)
                continue

            capacity_ready = refresh_worker_capacity(node, cluster_config)  # Valid capacity >0
            log.debug("cluster_api.pod.capacity", capacity_ready=capacity_ready, node=node.name)
            if capacity_ready:
                ready_nodes.append(node)

        for node in ready_nodes:
            log.debug("cluster_api.pod.should_be_ready", node=node.name, status=node.status)
            if node.status not in {WorkerStatus.IDLE, WorkerStatus.WORKING}:
                node.status = WorkerStatus.IDLE
                log_node_status_snapshot(cluster_config.cluster_config.name, node)
        if len(ready_nodes) == len(worker_nodes):
            return True

        time.sleep(poll_interval_s)

    for node in worker_nodes:
        if node.status not in {WorkerStatus.IDLE, WorkerStatus.WORKING}:
            node.status = WorkerStatus.OFF
            node.max_slots = 0
            log_node_status_snapshot(cluster_name, node)
            log.warning("cluster_api.power.pod_not_ready", cluster=cluster_name, node=node)

    return False


def change_node_status(number_of_nodes: int, status: str):
    """Turn a requested number of workers on or off.

    When turning on worker nodes, the operation is performed concurrently using
    threads because powering on a worker can take several seconds. This allows
    multiple nodes to start simultaneously instead of sequentially. The function
    still waits until all expected nodes are fully powered on before continuing.

    Args:
        number_of_nodes: Maximum number of workers to change.
        status: Either ``"on"`` or ``"off"``.

    Returns:
        A small summary dict with the requested count, action, and changed nodes.

    """
    cluster_config = config_store.get()
    cluster_name = cluster_config.cluster_config.name
    nodes = cluster_config.worker_nodes
    if status == "on":
        nodes_to_change = select_nodes_to_turn_on(number_of_nodes, nodes)
        with ThreadPoolExecutor(max_workers=max(1, len(nodes_to_change))) as executor:
            futures = [executor.submit(turn_on_node, node, cluster_name) for node in nodes_to_change]
            for future in futures:
                future.result()

        ready = wait_for_nodes_to_be_ready(nodes_to_change, cluster_name)

        if not ready:
            log.warning(
                "cluster_api.power.turn_on_nodes_not_all_ready",
                cluster_name=cluster_name,
                nodes=[node.name for node in nodes_to_change],
            )

    elif status == "off":
        nodes_to_change = select_nodes_to_turn_off(number_of_nodes, nodes)
        for node in nodes_to_change:
            turn_off_node(node, cluster_config.cluster_config.name)
    else:
        raise ValueError("status must be 'on' or 'off'")

    return {
        "requested": number_of_nodes,
        "status": status,
        "node_changed": len(nodes_to_change),
        "nodes": [node.name for node in nodes_to_change],
    }


def select_nodes_to_turn_on(number_of_nodes: int, worker_nodes: list[WorkerNode]) -> list[WorkerNode]:
    """Pick powered off workers that should be powered on.

    Args:
        number_of_nodes: Maximum number of workers to select.
        worker_nodes: Full worker list for the cluster.

    Returns:
        Workers selected for power-on, in the order they were found.

    """
    nodes_to_turn_on = []
    for node in worker_nodes:
        if len(nodes_to_turn_on) >= number_of_nodes:
            break
        if node.status == WorkerStatus.OFF:
            nodes_to_turn_on.append(node)
            continue

    return nodes_to_turn_on


def select_nodes_to_turn_off(number_of_nodes: int, worker_nodes: list[WorkerNode]) -> list[WorkerNode]:
    """Pick idle workers that should be powered off.

    Args:
        number_of_nodes: Maximum number of workers to select.
        worker_nodes: Full worker list for the cluster.

    Returns:
        Idle workers selected for power-off, in the order they were found.

    """
    nodes_to_turn_off = []
    for node in worker_nodes:
        if len(nodes_to_turn_off) >= number_of_nodes:
            break
        if node.status == WorkerStatus.IDLE:
            nodes_to_turn_off.append(node)
    return nodes_to_turn_off


def get_idle_time(node_name: str, cluster_name: str) -> float:
    """Return how long a worker has been idle.

    The function reads the latest node-status log entry for the worker. If the latest
    status is ``IDLE``, it returns the age of that state in seconds. If the node is not
    currently idle, it returns ``0`` so the caller does not treat it as eligible.

    Args:
        node_name: Name of the worker node.
        cluster_name: Name of the cluster the node belongs to.

    Returns:
        Number of seconds since the node last became idle, or ``0`` if it is not idle.

    """
    now = datetime.now(timezone.utc)

    try:
        config = config_store.get()
        config_id = config.config_id
        entry = get_worker_nodes_logs(config_id, cluster_name, node_name)
    except Exception as e:
        log.debug("cluster_api.power.get_worker_nodes_logs", error=str(e))
        return 0

    if entry is None:
        # No log entry found for this node; conservatively return 0 (don't turn off)
        return 0

    log.debug("cluster_api.power.entry_debug", entry=entry)
    log.debug("cluster_api.power.latest_node_change", status=entry.status)
    if str(entry.status).lower() == WorkerStatus.IDLE.value:
        log.debug("cluster_api.power.latest_node_change", changed=True)
        return (now - entry.timestamp).total_seconds()

    log.debug("cluster_api.power.latest_node_change", changed=False)
    return 0


def turn_off_idle_nodes(idle_time: int, stay_one: bool = False):
    """Turn off workers that have been idle longer than the configured threshold.

    Args:
        idle_time: Minimum idle time in seconds before a node may be powered off.
        stay_one: Keep one worker running when the cluster would otherwise drop to zero.

    Returns:
        A summary dict when the stay-one guard short-circuits; otherwise ``None``.

    """
    config = config_store.get()
    cluster_name = config.cluster_config.name
    config_id = config.config_id
    if not config_id:
        log.warning(
            "cluster_api.power.turn_off_idle_skipped_missing_config_id",
            cluster_name=cluster_name,
            worker_node=None,
        )
        return

    nodes = config.worker_nodes

    # Ensure the same working node (sorted by name) is never turned off.
    nodes = sorted(config.worker_nodes, key=lambda n: n.name)
    keeper = nodes[0]

    for node in nodes:
        if node is keeper:
            continue
        # Only true idle nodes are eligible for automatic power-off.
        if node.status != WorkerStatus.IDLE:
            log.debug(
                "cluster_api.power.turn_off_idle_skipped_status",
                cluster_name=cluster_name,
                worker_node=node.name,
                status=node.status,
            )
            continue

        # Never power off a node while requests are still inflight.
        if node.inflight_requests > 0:
            log.debug(
                "cluster_api.power.turn_off_idle_skipped_inflight",
                cluster_name=cluster_name,
                worker_node=node.name,
                inflight_requests=node.inflight_requests,
            )
            continue

        last_request = get_idle_time(node.name, cluster_name)
        log.debug("cluster_api.power.last_request", last_request=last_request)
        if last_request > idle_time:
            log.info(
                "cluster_api.power.turn_off_idle_node_selected",
                cluster_name=cluster_name,
                worker_node=node.name,
                last_request_age_s=last_request,
                idle_time_s=idle_time,
            )
            turn_off_node(node, cluster_name)
        else:
            log.debug(
                "cluster_api.power.turn_off_idle_skipped_recent_request",
                cluster_name=cluster_name,
                worker_node=node.name,
                last_request_age_s=last_request,
                idle_time_s=idle_time,
            )
