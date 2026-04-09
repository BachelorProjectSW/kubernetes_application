import lgpio
import paramiko
import structlog
from ...models.basemodels import WorkerNode
from ..util.cluster_config import config_store
from ...models.enum import WorkerStatus

log = structlog.get_logger()

h = lgpio.gpiochip_open(0)

def turn_on_node(worker_node: WorkerNode):
    """Turn on the node via GPIO."""
    try:
        gpio = worker_node.gpio
        log.debug("gpio to turn on", gpio=gpio)
        lgpio.gpio_claim_output(h, gpio)
        lgpio.gpio_write(h, gpio, 1)  # turn LED on
        log.debug("turning node on", node=worker_node.name)
        worker_node.status = WorkerStatus.IDLE
    except Exception as e:
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
        worker_node.status = WorkerStatus.OFF #DEBUG!!!
        log.debug(f"failed to shutdown node: {e}")


def change_node_status(number_of_nodes: int, status: str):
    """Change status of up to number_of_nodes in the cluster.

    status: 'on' or 'off'.
    """
    cluster_config = config_store.get()
    nodes = cluster_config.worker_nodes
    node_changed = 0
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
