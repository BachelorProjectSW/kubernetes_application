from fastapi import APIRouter

from cluster_api.services.forward_llm_question import forward_llm_question
from models.basemodels import Question
from ..services.nodes import get_cluster_working_nodes
from ..services.power_scheduler import change_node_status
router = APIRouter()


@router.get("/get_cluster_working_nodes/")
def nodes(cluster_name: str):
    """Return all working nodes."""
    return get_cluster_working_nodes(cluster_name)

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

@router.post("/turn_on_nodes/")
def turn_on_node_endpoint(number_of_nodes: int):
    """Return status of turning on nodes."""
    return change_node_status(number_of_nodes, "on")


@router.post("/turn_off_nodes/")
def turn_off_node_endpoint(number_of_nodes: int):
    """Return status of turned off nodes."""
    return change_node_status(number_of_nodes, "off")
