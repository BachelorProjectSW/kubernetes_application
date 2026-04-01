from fastapi import APIRouter
from ...models.basemodels import Question
from ..services.forward_llm_question import forward_llm_question
from ..services.get_worker_nodes import get_cluster_working_nodes
router = APIRouter()


@router.get("/get_cluster_working_nodes")
def nodes():
    """Return all working nodes."""
    return get_cluster_working_nodes()


@router.post("/forward_llm_question")
def forward_llm_question_route(question: Question):
    """Forward a question to the llama service."""
    try:
        result = forward_llm_question(
            question=question.question,
            n_predict=question.n_predict,
        )
        return result.get("content", result)
    except Exception as e:
        raise RuntimeError(f"Failed forwarding the question: {e}") from e
