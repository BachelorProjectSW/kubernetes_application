from fastapi import APIRouter
from cluster_api.services.get_worker_nodes import get_worker_nodes

router = APIRouter()


@router.get("/nodes")
def nodes():
    """Return all working nodes."""
    return get_worker_nodes()
