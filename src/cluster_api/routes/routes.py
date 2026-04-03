from fastapi import APIRouter
from ..services.nodes import cluster_store 
from ..services.power_scheduler import change_node_status
from ..services.llm import handle_llm
from ...models.basemodels import ClusterInformation
from ..util.cluster_config import config_store
router = APIRouter()


@router.get("/get_cluster_working_nodes/")
def nodes(cluster_name: str):
    """Return all working nodes."""
    return cluster_store.to_dict()


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
    return config_store.set(cluster_information)


@router.post("/handle_llm_request")
def handle_llm_request_endpoint(question: str):
    """Handle llm request."""
    return handle_llm(question)