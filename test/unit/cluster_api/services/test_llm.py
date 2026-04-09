import pytest
from unittest.mock import Mock
from ...models.basemodels import QuestionConfig, WorkerNode
import src.cluster_api.services.llm as llm

# helper functions
def make_worker(
    name: str,
    status: str = "idle",
    slots_in_use: int = 0,
    max_slots: int = 4,
    ip: str = "127.0.0.1",
) -> WorkerNode:
    return WorkerNode(
        name=name,
        ip=ip,
        status=status,
        slots_in_use=slots_in_use,
        max_slots=max_slots,
        gpio=1,
    )

@pytest.fixture(autouse=True)
def reset_rr_index():
    llm.rr_index = 0


def test_round_robin_cycles_in_sorted_order():
    workers = [
        make_worker("node-c"),
        make_worker("node-a"),
        make_worker("node-b"),
    ]

    assert llm.round_robin(workers).name == "node-a"
    assert llm.round_robin(workers).name == "node-b"
    assert llm.round_robin(workers).name == "node-c"
    assert llm.round_robin(workers).name == "node-a"
