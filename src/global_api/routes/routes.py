from fastapi import APIRouter
from ..services.get_all_worker_nodes import get_all_worker_nodes
from ..services.handle_llm_request import handle_llm_request
from ...models.basemodels import Question
router = APIRouter()


@router.get("/get_all_cluster_nodes")
def nodes():
    """Return all working nodes."""
    return get_all_worker_nodes()

@router.post("/handle_llm_question")
def handle_llm_question(question: Question):
    """Handle llm question"""
    return print(question.question)
    #return handle_llm_request(question.question)