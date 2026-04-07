from fastapi import APIRouter, HTTPException
from ..services.get_all_worker_nodes import get_all_worker_nodes
from ..services.handle_llm_request import handle_llm_request
from ..services.start_test import start_test, stop_test
from ...models.basemodels import Config, QuestionConfig
router = APIRouter()


@router.get("/get_all_clusters_working_nodes")
def nodes():
    """Return all working nodes."""
    return get_all_worker_nodes()


@router.post("/handle_llm_question")
def handle_llm_question(question: QuestionConfig):
    """Handle llm question."""
    return handle_llm_request(question)


@router.post("/start_test")
def start_test_endpoint(config: Config):
    """Start the test"""
    try:
        return start_test(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop_test")
def stop_test_endpoint():
    """Stop current test"""
    return stop_test()