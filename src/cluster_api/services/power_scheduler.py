from gpiozero import LED as IO
import paramiko
import structlog
from ...models.basemodels import WorkerNode
from .nodes import cluster_service  

log = structlog.get_logger()


def turn_on_node(worker_node: WorkerNode):
    """Turn on the node via GPIO."""
    gpio = worker_node.gpio 
    log.debug("gpio to turn on", gpio=gpio)
    IO(gpio).on()
    log.debug("turning node on", node=worker_node.dict())
    worker_node.status = "on"


def turn_off_node(worker_node: WorkerNode, username: str, password: str):
    """Turn off the node using SSH."""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=worker_node.ip, username=username, password=password)

        stdin, stdout, stderr = client.exec_command("sudo shutdown now")
        stdin.write(password + "\n")
        stdin.flush()

        log.debug(stdout.read().decode())
        log.debug(stderr.read().decode())

        client.close()
        log.debug("turning node off", node=worker_node.dict())
        worker_node.status = "off"
    except Exception as e:
        log.debug("failed to shutdown node", e)


def change_node_status(number_of_nodes: int, status: str):
    """
    Change status of up to number_of_nodes in the cluster.
    status: 'on' or 'off'
    """
    nodes = cluster_service.worker_nodes

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
        if node.status == "off":
            nodes_to_turn_on.append(node)
    return nodes_to_turn_on


def select_nodes_to_turn_off(number_of_nodes: int, worker_nodes: list[WorkerNode]) -> list[WorkerNode]:
    """Select active nodes to turn off."""
    nodes_to_turn_off = []
    for node in worker_nodes:
        if len(nodes_to_turn_off) >= number_of_nodes:
            break
        if node.status == "on":
            nodes_to_turn_off.append(node)
    return nodes_to_turn_off