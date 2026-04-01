from gpiozero import LED as IO

from .nodes import Cluster, WorkerNode, get_cluster

def turn_on_node(worker_node: WorkerNode):
    """Turn on the node."""
    gpio = worker_node.gpio
    #IO(gpio).on()
    print("turning node on")
    worker_node.status = "Turning on"


def turn_on_nodes(number_of_nodes: int, cluster_name: str = "dk"):
    """Turn on up to number_of_nodes inactive nodes in a cluster."""
    cluster = get_cluster(cluster_name)
    nodes_to_turn_on = select_nodes_to_turn_on(number_of_nodes, cluster)

    for node in nodes_to_turn_on:
        turn_on_node(node)

    return {
        "cluster": cluster_name,
        "requested": number_of_nodes,
        "turned_on": len(nodes_to_turn_on),
        "nodes": [node.name for node in nodes_to_turn_on],
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