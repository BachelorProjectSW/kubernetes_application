from gpiozero import LED as IO
import paramiko
import structlog
from .nodes import Cluster, WorkerNode, get_cluster

log = structlog.get_logger()


def turn_on_node(worker_node: WorkerNode):
    """Turn on the node."""
    gpio = worker_node.gpio
    #IO(gpio).on()
    log.debug("turning node on", node=worker_node.to_dict)
    worker_node.status = "active"


def turn_off_node(worker_node: WorkerNode, username: str, password: str):
    try:
        # client = paramiko.SSHClient()
        # client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # client.connect(hostname=worker_node.ip, username=username, password=password)

        # stdin, stdout, stderr = client.exec_command("sudo shutdown now")

        # stdin.write(password + "\n")
        # stdin.flush()

        # log.debug(stdout.read().decode())
        # log.debug(stderr.read().decode())

        # client.close()
        log.debug("turning node off", node=worker_node.to_dict)
        worker_node.status = 'inactive'
    except Exception as e:
        log.debug("failed to shutdown node", e)


def change_node_status(number_of_nodes: int, status: str):
    """Turn on up to number_of_nodes inactive nodes in a cluster.
    status is either 'on' of 'off' """
    cluster = get_cluster()

    if status == "on":
        nodes_to_change = select_nodes_to_turn_on(number_of_nodes, cluster)
        for node in nodes_to_change:
            turn_on_node(node)
    elif status == "off":
        nodes_to_change = select_nodes_to_turn_off(number_of_nodes, cluster)
        for node in nodes_to_change:
            turn_off_node(node, cluster.name, cluster.name)
    
    return {
        "cluster": cluster.name,
        "requested": number_of_nodes,
        "status": status,
        "node_changed": len(nodes_to_change),
        "nodes": [node.name for node in nodes_to_change],
    }


def select_nodes_to_turn_on(number_of_nodes: int, cluster: Cluster) -> list[WorkerNode]:
    """This is just template code."""
    nodes_to_turn_on = []
    for node in cluster.nodes:
        if len(nodes_to_turn_on) >= number_of_nodes:
            break
        if node.status == "inactive":
            nodes_to_turn_on.append(node)
    return nodes_to_turn_on


def select_nodes_to_turn_off(number_of_nodes: int, cluster: Cluster) -> list[WorkerNode]:
    """This is just template code."""
    nodes_to_turn_off = []
    for node in cluster.nodes:
        if len(nodes_to_turn_off) >= number_of_nodes:
            break
        if node.status == "active":
            nodes_to_turn_off.append(node)
    return nodes_to_turn_off


