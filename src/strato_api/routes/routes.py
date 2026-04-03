from fastapi import APIRouter
from ..services.queue import config_manager
from ..services.start_test import start_test, start_test_test
from ...models.basemodels import Config
router = APIRouter()


@router.post("/add_test_to_queue")
def add_test_to_queue_endpoint(config: Config):
    """Add test to queue."""
    return config_manager.add_to_queue(config)


@router.delete("/delete_test_from_queue")
def delete_test_from_queue_endpoint(config_id: str):
    """Delete test from queue."""
    return config_manager.remove_from_queue(config_id)


@router.post("/start_test")
def start_test_endpoint(config: Config):
    """Start the test"""
    return start_test(config)


@router.post("/start_test_test")
def start_test_test_endpoint():
    """Start the test test"""
    return start_test_test()

