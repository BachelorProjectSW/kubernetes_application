import paramiko
import structlog
from ...models.basemodels import WorkerNode
from ..util.cluster_config import config_store
from ...models.enum import WorkerStatus
from ...custom_logging.util.log_reader import get_request_logs
from ...custom_logging.models.log_models import RequestLog
from datetime import datetime, timezone

import os

if os.environ.get("CI"):
    print("Running in CI – skipping GPIO initialization")
    h = None
else:
    import lgpio
    h = lgpio.gpiochip_open(0)

log = structlog.get_logger()


def turn_on_node(worker_node: WorkerNode):
    """Turn on the node via GPIO."""
    try:
        gpio = worker_node.gpio
        log.debug("gpio to turn on", gpio=gpio)
        lgpio.gpio_claim_output(h, gpio)
        lgpio.gpio_write(h, gpio, 1)  # turn LED on
        log.debug("turning node on", node=worker_node.name)
        worker_node.status = WorkerStatus.IDLE #Should be turning on
    except Exception as e:
        worker_node.status = WorkerStatus.IDLE #DEBUG!!!
        log.debug(f"failed to turn on node: {e}")


def turn_off_node(worker_node: WorkerNode, username: str, password: str):
    """Turn off the node using SSH."""
    try:
        gpio = worker_node.gpio
        log.debug("gpio to turn off", gpio=gpio)
        lgpio.gpio_claim_output(h, gpio)
        lgpio.gpio_write(h, gpio, 0)  # turn LED on
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=worker_node.ip, username=username, password=password)

        stdin, stdout, stderr = client.exec_command("sudo shutdown now")
        stdin.write(password + "\n")
        stdin.flush()

        log.debug(stdout.read().decode())
        log.debug(stderr.read().decode())

        client.close()
        log.debug("turning node off", node=worker_node.name)
        worker_node.status = WorkerStatus.OFF
    except Exception as e:
        worker_node.status = WorkerStatus.OFF  # DEBUG!!!
        log.debug(f"failed to shutdown node: {e}")


def change_node_status(number_of_nodes: int, status: str):
    """Change status of up to number_of_nodes in the cluster.

    status: 'on' or 'off'.
    """
    cluster_config = config_store.get()
    nodes = cluster_config.worker_nodes
    if status == "on":
        nodes_to_change = select_nodes_to_turn_on(number_of_nodes, nodes)
        for node in nodes_to_change:
            turn_on_node(node)
    elif status == "off":
        nodes_to_change = select_nodes_to_turn_off(number_of_nodes, nodes)
        for node in nodes_to_change:
            turn_off_node(node, username=node.name, password=node.name)
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
    """Select active nodes to turn off."""
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
            turn_off_node(node, node.name, node.name)
