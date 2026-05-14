from fastapi import APIRouter, HTTPException, Request

from ..services.validate_config import validate_config
from ..services.get_all_worker_nodes import get_all_worker_nodes
from ..services.handle_llm_request import handle_llm_request
from ..services.start_test import start_test, stop_test
from ...models.basemodels import Config, QuestionConfig
router = APIRouter()


@router.get("/get_all_clusters_working_nodes")
def nodes():
    """Return all worker nodes that are currently available for scheduling.

    This endpoint is typically used by dashboards or diagnostics to show which
    nodes can accept new work right now.

    Returns:
        List of worker-node entries from all clusters.

    """
    return get_all_worker_nodes()


@router.post("/handle_llm_question")
def handle_llm_question(question: QuestionConfig, request: Request):
    """Send an LLM question through the global scheduler.

    Reads an optional trace ID from the `X-Trace-Id` request header and passes
    it along so logs from multiple services can be correlated.

    Args:
        question: User question payload and related request settings.
        request: FastAPI request object used for reading headers.

    Returns:
        Scheduler response containing the chosen cluster and model output.

    """
    trace_id = request.headers.get("X-Trace-Id")
    return handle_llm_request(question, trace_id=trace_id)


@router.post("/start_test")
def start_test_endpoint(config: Config):
    """Start a new test run using the provided configuration.

    Args:
        config: Full test configuration, including cluster setup and timing.

    Returns:
        Start-test response from the service layer.

    Raises:
        HTTPException: If the test cannot be started.

    """
    try:
        return start_test(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop_test")
def stop_test_endpoint():
    """Stop the currently running test and perform shutdown cleanup.

    Returns:
        Stop-test response describing what was stopped.

    """
    return stop_test()


@router.post("/validate_config")
def validate_config_endpoint(config: Config):
    """Validate a test configuration before execution.

    This endpoint checks that required values and constraints are valid so users
    get fast feedback before starting a potentially long test run.

    Args:
        config: Configuration object to validate.

    Returns:
        Validation result with pass/fail status and any validation messages.

    """
    return validate_config(config)
