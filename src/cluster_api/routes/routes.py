from fastapi import APIRouter
from ..services.nodes import get_cluster_working_nodes
from ..services.power_scheduler import turn_on_nodes
router = APIRouter()


@router.get("/get_cluster_working_nodes")
def nodes():
    """Return all working nodes."""
    return get_cluster_working_nodes()

@router.post("/turn_on_nodes/{number_of_nodes}")
def turn_on_node_endpoint(number_of_nodes: int):
    """Return status of turning on node."""
    return turn_on_nodes(number_of_nodes)
