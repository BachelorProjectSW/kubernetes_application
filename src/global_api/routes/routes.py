from fastapi import APIRouter, HTTPException, Request

from ..services.validate_config import validate_config
from ..services.get_all_worker_nodes import get_all_worker_nodes
from ..services.handle_llm_request import handle_llm_request
from ..services.start_test import start_test, stop_test
from ...models.basemodels import Config, QuestionConfig
from ..services.test_state import test_state
router = APIRouter()


@router.get("/get_all_clusters_working_nodes")
def nodes():
    """Return all working nodes."""
    return get_all_worker_nodes()


@router.post("/handle_llm_question")
async def handle_llm_question(question: QuestionConfig, request: Request):
    """Handle llm question."""
    trace_id = request.headers.get("X-Trace-Id")
    return await handle_llm_request(question, trace_id=trace_id)


@router.post("/start_test")
def start_test_endpoint(config: Config):
    """Start the test."""
    try:
        return start_test(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop_test")
def stop_test_endpoint():
    """Stop current test."""
    return stop_test()


@router.post("/validate_config")
def validate_config_endpoint(config: Config):
    """Validate config before starting test."""
    return validate_config(config)

@router.get("/test_status")
def test_status_endpoint():
    if test_state.is_stopping():
        return {"status": "stopping"}
    if test_state.is_running():
        return {"status": "running"}
    return {"status": "idle"}
