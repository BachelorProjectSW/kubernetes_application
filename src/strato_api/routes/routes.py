from fastapi import APIRouter
from ..services.queue import config_manager
from ..services.start_test import start_test, start_test_test
from ...models.basemodels import Config
router = APIRouter()


@router.post("/start_test")
def start_test_endpoint(config: Config):
    """Start the test."""
    return start_test(config)


@router.post("/start_test_test")
def start_test_test_endpoint():
    """Start the test test."""
    return start_test_test()
