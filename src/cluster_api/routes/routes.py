from fastapi import APIRouter
from ..services.get_worker_nodes import get_cluster_nodes
from ..services.handle_question_request import handle_question_request
from ..models.basemodels import Question

router = APIRouter()


@router.get("/get_cluster_nodes")
def nodes():
    """Return all working nodes."""
    return get_cluster_nodes()




@router.post("/llm_question")
def llm(question: Question):
    return handle_question_request(question.question)

