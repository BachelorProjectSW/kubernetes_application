from fastapi import APIRouter, HTTPException
from ..services.start_test import start_test, start_test_test, stop_test, get_test_status
from ...models.basemodels import Config
router = APIRouter()


@router.post("/start_test")
def start_test_endpoint(config: Config):
    """Start the test."""
    try:
        return start_test(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start_test_test")
def start_test_test_endpoint():
    """Start the test test."""
    try:
        return start_test_test()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop_test")
def stop_test_endpoint():
    """Stop the test."""
    try:
        return stop_test()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test_status")
def test_status_endpoint():
    """Return current test status: idle, running, or stopping."""
    return get_test_status()
