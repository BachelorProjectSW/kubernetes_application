from fastapi import APIRouter, HTTPException
from ..services.start_test import start_test, start_test_test, stop_test, get_test_status
from ..services.test_results import get_test_results
from ...models.basemodels import Config
from ...db.postgres import read_all_configs
router = APIRouter()


@router.post("/start_test")
def start_test_endpoint(config: Config):
    """Start a test run using a caller-provided configuration.

    This endpoint forwards the validated config payload to the Strato service
    layer and returns its startup response.

    Args:
        config: Full test configuration payload.

    Returns:
        Any: Service response describing the started test.

    Raises:
        HTTPException: ``500`` if the underlying service raises an exception.

    """
    try:
        return start_test(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start_test_test")
def start_test_test_endpoint():
    """Start the predefined test scenario used for testing.

    This endpoint triggers an internal helper that starts a known test setup
    without requiring a request body.

    Returns:
        Any: Service response describing the started predefined test.

    Raises:
        HTTPException: ``500`` if the underlying service raises an exception.

    """
    try:
        return start_test_test()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop_test")
def stop_test_endpoint():
    """Stop the currently running test workflow.

    Returns:
        Any: Service response confirming stop behavior.

    Raises:
        HTTPException: ``409`` if a stop conflict occurs.
        HTTPException: ``500`` for other unexpected failures.

    """
    try:
        return stop_test()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test_status")
def test_status_endpoint():
    """Return the current lifecycle state of the test runner.

    Returns:
        Any: Current status payload, typically indicating ``idle``,
        ``running``, or ``stopping``.

    """
    return get_test_status()


@router.get("/test_results")
def test_results_endpoint(config_id: str):
    """Return stored test results and summary data for one config id for frontend output.

    Args:
        config_id: Identifier of the configuration whose results are requested.

    Returns:
        Any: Persisted test results and graph-ready summary payload.

    Raises:
        HTTPException: Re-raised service-level HTTP errors.
        HTTPException: ``500`` for unexpected failures.

    """
    try:
        return get_test_results(config_id)
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_configs")
def get_config_endpoint():
    """Return all stored configurations serialized as JSON-compatible dicts.

    Returns:
        list[dict]: All configurations currently stored in the database.

    Raises:
        HTTPException: Re-raised service-level HTTP errors.
        HTTPException: ``500`` for unexpected failures.



    """
    try:
        return [config.model_dump(mode="json") for config in read_all_configs()]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
