from fastapi import APIRouter, Request
from ..services.cancel_all_llama_pods import cancel_all_llama_pods
from ..services.power_scheduler import change_node_status, turn_off_idle_nodes
from ..services.llm import handle_llm
from ...models.basemodels import ClusterInformation, QuestionConfig
from ...custom_logging.logger import set_current_config_id
from ..util.cluster_config import config_store
router = APIRouter()


@router.get("/get_cluster_working_nodes")
def nodes():
    """Show the worker nodes that the cluster API knows about.

    Returns:
        The current worker-node list as plain JSON data.

    """
    return config_store.get_worker_nodes_dict()


@router.post("/turn_on_nodes/")
def turn_on_node_endpoint(number_of_nodes: int):
    """Turn on a requested number of nodes in the cluster.

    Args:
        number_of_nodes: How many nodes should be powered on.

    Returns:
        The result from the node power-control logic.

    """
    return change_node_status(number_of_nodes, "on")


@router.post("/turn_off_nodes/")
def turn_off_node_endpoint(number_of_nodes: int):
    """Turn off a specified number of nodes in the cluster.

    This is intended for debugging and manual testing only and is not used in
    production environments.

    Args:
        number_of_nodes: The number of nodes to power off.

    Returns:
        The result returned by the node power-control logic.

    """
    return change_node_status(number_of_nodes, "off")


@router.post("/turn_off_idle_nodes/")
def turn_off_idle_nodes_endpoint(idle_time: int, stay_one: bool = True):
    """Turn off nodes that have been idle for too long.

    Args:
        idle_time: Duration a node must remain idle before it is eligible to be shut down.

        stay_one: Whether to always keep one node running, even when the cluster is idle.
            Defaults to `True` to ensure at least one worker node remains available
            for each cluster.

    Returns:
        The result from the idle-node shutdown logic.

    """
    return turn_off_idle_nodes(idle_time, stay_one=stay_one)


@router.post("/set_config")
def set_config(cluster_information: ClusterInformation):
    """Store a new cluster configuration and rebuild the worker list.

    Args:
        cluster_information: The full cluster configuration to load.

    Returns:
        The stored cluster configuration after it has been applied.

    """
    set_current_config_id(cluster_information.config_id)
    config_store.set(cluster_information)
    config_store.build_worker_nodes()
    return config_store.get()


@router.post("/handle_llm_request")
def handle_llm_request_endpoint(question: QuestionConfig, request: Request):
    """Send a question to the LLM handler for this cluster.

    Args:
        question: The question payload that should be handled by the model.
        request: The incoming HTTP request, used here to read the trace id for debugging.

    Returns:
        The LLM handler response.

    """
    trace_id = request.headers.get("X-Trace-Id")
    return handle_llm(question, trace_id=trace_id)


@router.get("/get_cluster_information")
def get_cluster_information_endpoint():
    """Return the full cluster configuration currently in memory.

    Returns:
        The active cluster information object.

    """
    return config_store.get()


@router.post("/cancel_all_llama_pods")
def cancel_all_llama_pods_endpoint():
    """Delete every running llama pod so they can be restarted cleanly.

    Returns:
        A short status message confirming the restart request.

    """
    cancel_all_llama_pods()
    return {"message": "Llama pods deleted, restarting"}
