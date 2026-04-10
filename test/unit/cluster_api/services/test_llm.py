import pytest
from src.models.basemodels import WorkerNode
import src.cluster_api.services.llm as llm


def make_worker(

    name: str,
    status: str = "idle",
    inflight_requests: int = 0,
    max_slots: int = 4,
    ip: str = "127.0.0.1",
) -> WorkerNode:
    """Make a worker."""
    return WorkerNode(
        name=name,
        ip=ip,
        status=status,
        inflight_requests=inflight_requests,
        max_slots=max_slots,
        gpio=1,
    )


@pytest.fixture(autouse=True)
def reset_rr_index():
    """Reset the round robin index."""
    llm.rr_index = 0


def test_round_robin_cycles_in_sorted_order():
    """Test to check whether round robin works (it chooses the next in the list)."""
    workers = [
        make_worker("node-c"),
        make_worker("node-a"),
        make_worker("node-b"),
    ]

    assert llm.round_robin(workers).name == "node-a"
    assert llm.round_robin(workers).name == "node-b"
    assert llm.round_robin(workers).name == "node-c"
    assert llm.round_robin(workers).name == "node-a"


def test_choose_worker_node_prefers_idle_worker():
    """Test to check whether it chooses the idle node."""
    workers = [
        make_worker("node-b", status="working", inflight_requests=1, max_slots=4),
        make_worker("node-a", status="idle", inflight_requests=0, max_slots=4),
    ]

    chosen = llm.choose_worker_node(workers)
    assert chosen is not None
    assert chosen.name == "node-a"


def test_choose_worker_node_picks_worker_with_most_free_slots():
    """Chooses the worker with the most free slots."""
    workers = [
        make_worker("node-a", status="working", inflight_requests=3, max_slots=4),  # 1 free
        make_worker("node-b", status="working", inflight_requests=1, max_slots=4),  # 3 free
        make_worker("node-c", status="working", inflight_requests=2, max_slots=4),  # 2 free
    ]

    chosen = llm.choose_worker_node(workers)
    assert chosen is not None
    assert chosen.name == "node-b"


def test_choose_worker_node_picks_first_sorted_when_multiple_best_with_free_slots():
    """Chooses the first node in a name sorted list, when multiple have same amount of free slots."""
    workers = [
        make_worker("node-b", status="working", inflight_requests=1, max_slots=4),  # 3 free
        make_worker("node-a", status="working", inflight_requests=1, max_slots=4),  # 3 free
        make_worker("node-c", status="working", inflight_requests=2, max_slots=4),  # 2 free
    ]

    chosen = llm.choose_worker_node(workers)
    assert chosen is not None
    assert chosen.name == "node-a"


def test_choose_worker_node_uses_round_robin_when_all_best_workers_are_full_or_overloaded():
    """Uses round robin when all are filled up."""
    workers = [
        make_worker("node-b", status="working", inflight_requests=4, max_slots=4),  # 0 free
        make_worker("node-a", status="working", inflight_requests=4, max_slots=4),  # 0 free
        make_worker("node-c", status="working", inflight_requests=5, max_slots=4),  # queued
    ]

    first = llm.choose_worker_node(workers)
    second = llm.choose_worker_node(workers)

    assert first is not None
    assert second is not None
    assert first.name == "node-a"
    assert second.name == "node-b"
