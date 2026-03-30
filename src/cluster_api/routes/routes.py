from fastapi import APIRouter
from ..services.get_worker_nodes import get_cluster_working_nodes
router = APIRouter()


@router.get("/get_cluster_working_nodes")
def nodes():
    """Return all working nodes."""
    return get_cluster_working_nodes()
