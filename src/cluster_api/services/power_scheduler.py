import paramiko
import structlog
from concurrent.futures import ThreadPoolExecutor
from ...models.basemodels import WorkerNode
from ..util.cluster_config import config_store
from ..util.client_setup import get_api_client
from ...models.enum import WorkerStatus
from ...custom_logging.util.log_reader import get_request_logs
from ...custom_logging.models.log_models import RequestLog
from datetime import datetime, timezone
import subprocess
import time
from ...custom_logging.logger import log_node_status_snapshot

log = structlog.get_logger()


def run_cmd(cmd):
    """Run bash command."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def turn_on_node(worker_node: WorkerNode, cluster_name: str):
    """Turn on the node via GPIO."""
    try:
        gpio = worker_node.gpio
        log.debug("gpio to turn on", gpio=gpio)
        run_cmd(f"sudo gpioset gpiochip4 {gpio}=1")
        time.sleep(0.5)
        run_cmd(f"sudo gpioset gpiochip4 {gpio}=0")
        log.debug("turning node on", node=worker_node.name)
        worker_node.status = WorkerStatus.TURNING_ON
        log_node_status_snapshot(cluster_name, worker_node)
        return True
    except Exception as e:
        log.debug(f"failed to turn on node: {e}")
        return False


def turn_off_node(worker_node: WorkerNode, cluster_name: str):
    """Turn of node with SSH."""
    try:
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

        log.debug("power.turn.off", STDOUT=out)
        log.debug("power.turn.off", STDERR=err)

        client.close()

        worker_node.status = WorkerStatus.OFF
        log_node_status_snapshot(cluster_name, worker_node)
        return True
    except Exception as e:
        log.debug("power.error", error=e)
        return False


def check_if_llama_pod_is_ready(worker_node: WorkerNode, api_client, namespace: str = "default") -> bool:
    """Return True when a llama pod on this node is Running and Ready."""
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
            pod_ready = any(c.type == "Ready" and c.status == "True" for c in conditions)

            container_statuses = getattr(pod.status, "container_statuses", None) or []
            containers_ready = bool(container_statuses) and all(cs.ready for cs in container_statuses)

            if pod_ready and containers_ready:
                return True

        return False

    except Exception as e:
        log.debug("power.pod_readiness_check_failed", node=worker_node.name, error=str(e))
        return False


def wait_for_nodes_to_be_ready(
        worker_nodes: list[WorkerNode],
        cluster_name: str,
        timeout_s: int = 120,
        poll_interval_s: int = 2
        ) -> bool:
    """Wait until each selected node has a Running+Ready llama pod."""
    deadline = time.time() + timeout_s
    api_client = get_api_client()

    while time.time() < deadline:
        ready_nodes = [node for node in worker_nodes if check_if_llama_pod_is_ready(node, api_client)]

        for node in ready_nodes:
            node.status = WorkerStatus.IDLE
            log_node_status_snapshot(cluster_name, node)

        if len(ready_nodes) == len(worker_nodes):
            return True

        time.sleep(poll_interval_s)

    return False


def change_node_status(number_of_nodes: int, status: str):
    """Change status of up to number_of_nodes in the cluster.

    status: 'on' or 'off'.
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

        all_ready = wait_for_nodes_to_be_ready(nodes_to_change, cluster_name)
        if not all_ready:
            log.warning("power.nodes_not_ready_before_timeout", nodes=[node.name for node in nodes_to_change])

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
    """Select inactive nodes to turn on."""
    nodes_to_turn_on = []
    for node in worker_nodes:
        if len(nodes_to_turn_on) >= number_of_nodes:
            break
        if node.status == WorkerStatus.OFF:
            nodes_to_turn_on.append(node)
    return nodes_to_turn_on


def select_nodes_to_turn_off(number_of_nodes: int, worker_nodes: list[WorkerNode]) -> list[WorkerNode]:
    """Select active nodes to turn off, this is only used for manually turn off x nodes."""
    nodes_to_turn_off = []
    for node in worker_nodes:
        if len(nodes_to_turn_off) >= number_of_nodes:
            break
        if node.status == WorkerStatus.IDLE:
            nodes_to_turn_off.append(node)
    return nodes_to_turn_off


def get_idle_time(request_logs: list[RequestLog], node_name: str, cluster_name: str) -> float:
    """Return the idle time in seconds for a given node in a cluster.

    Args:
        request_logs: List of RequestLog entries.
        node_name: Name of the node to check.
        cluster_name: Name of the cluster the node belongs to.

    Returns:
        Time in seconds since the last request handled by this node.
        Returns a very large number if the node has never handled a request.

    """
    now = datetime.now(timezone.utc)

    # Iterate in reverse to find the latest request first
    for request in reversed(request_logs):
        if request.cluster == cluster_name and request.node == node_name:
            return (now - request.timestamp).total_seconds()

    # If no requests found
    return float('inf')


def turn_off_idle_nodes(idle_time: int):
    """Turn off all nodes that have been idle for longer than `idle_time` seconds.

    Args:
        idle_time: Number of seconds a node must be idle before being turned off.

    """
    config = config_store.get()
    cluster_name = config.cluster_config.name
    request_logs = get_request_logs()
    nodes = config.worker_nodes

    for node in nodes:
        if node.status != WorkerStatus.IDLE:
            continue
        last_request = get_idle_time(request_logs, node.name, cluster_name)
        if last_request > idle_time:
            turn_off_node(node, cluster_name)
