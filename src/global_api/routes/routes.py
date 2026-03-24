from fastapi import APIRouter
from ..services.get_all_worker_nodes import get_all_worker_nodes
router = APIRouter()


@router.get("/get_all_cluster_nodes")
def nodes():
    """Return all working nodes."""
    return get_all_worker_nodes()
