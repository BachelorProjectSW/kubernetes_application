from fastapi import APIRouter
from ..services.power_scheduler import change_node_status
from ..services.llm import handle_llm
from ...models.basemodels import ClusterInformation, QuestionConfig
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


@router.post("/set_config")
def set_config(cluster_information: ClusterInformation):
    """Set the config in util."""
    config_store.set(cluster_information)
    config_store.build_worker_nodes() 
    return config_store.get()


@router.post("/handle_llm_request")
def handle_llm_request_endpoint(question: QuestionConfig):
    """Handle llm request."""
    return handle_llm(question)