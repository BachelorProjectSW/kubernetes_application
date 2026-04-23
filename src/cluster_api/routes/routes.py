from fastapi import APIRouter,Request

from ..services.test_state import test_state
from ..services.cancel_all_llama_pods import cancel_all_llama_pods
from ..services.power_scheduler import change_node_status, turn_off_idle_nodes
from ..services.llm import handle_llm
from ...models.basemodels import ClusterInformation, QuestionConfig
from ...custom_logging.logger import set_current_config_id
from ..util.cluster_config import config_store
router = APIRouter()


@router.get("/get_cluster_working_nodes")
def nodes():
    """Return all working nodes."""
    return config_store.get_worker_nodes_dict()


@router.post("/turn_on_nodes/")
def turn_on_node_endpoint(number_of_nodes: int):
    """Return status of turning on nodes."""
    return change_node_status(number_of_nodes, "on")


@router.post("/turn_off_nodes/")
def turn_off_node_endpoint(number_of_nodes: int):
    """Return status of turned off nodes."""
    return change_node_status(number_of_nodes, "off")


@router.post("/turn_off_idle_nodes/")
def turn_off_idle_nodes_endpoint(idle_time: int):
    """Return status of turned off nodes."""
    return turn_off_idle_nodes(idle_time)


@router.post("/set_config")
def set_config(cluster_information: ClusterInformation):
    """Set the config in util."""
    set_current_config_id(cluster_information.config_id)
    config_store.set(cluster_information)
    test_state.start()
    config_store.build_worker_nodes()
    return config_store.get()


@router.post("/handle_llm_request")
def handle_llm_request_endpoint(question: QuestionConfig, request: Request):
    """Handle llm request."""
    trace_id = request.headers.get("X-Trace-Id")
    return handle_llm(question, trace_id=trace_id)


@router.get("/get_cluster_information")
def get_cluster_information_endpoint():
    """Return cluster information."""
    return config_store.get()


@router.post("/cancel_all_llama_pods")
def cancel_all_llama_pods_endpoint():
    """Delete all llama pods."""
    cancel_all_llama_pods()
    return {"message": "Llama pods deleted, restarting"}

@router.post("/stop_test")
def stop_test_endpoint():
    test_state.mark_stopping()
    return {"message": "Cluster stopping"}

@router.post("/refresh_worker_capacities")
def refresh_worker_capacities():
    config_store.populate_worker_capacities()
    return {"message": "refreshed"}