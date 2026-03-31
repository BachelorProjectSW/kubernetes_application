from fastapi import APIRouter
from ..services.get_worker_nodes import get_cluster_working_nodes
from ..services.power_scheduler import turn_on_node
router = APIRouter()


@router.get("/get_cluster_working_nodes")
def nodes():
    """Return all working nodes."""
    return get_cluster_working_nodes()

@router.post("turn_on_node/{gpio}")
def turn_on_node_endpoint(gpio: int):
    """Return status of turning on node."""
    return turn_on_node(gpio) 
