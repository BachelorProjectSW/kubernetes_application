import pytest

from src.cluster_api.services import llm
from src.models.enum import WorkerStatus
from test.k3d.cluster_configs.worker_nodes import UnitTestWorkerNodes


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_round_robin_index():
    """Reset round-robin state before each test so cases stay independent."""
    llm.rr_index = 0


def test_round_robin_returns_workers_in_name_order_and_wraps():
    """Round-robin should rotate through workers in sorted name order."""
    workers = [
        UnitTestWorkerNodes.make("worker-c", WorkerStatus.IDLE, 3),
        UnitTestWorkerNodes.make("worker-a", WorkerStatus.IDLE, 1),
        UnitTestWorkerNodes.make("worker-b", WorkerStatus.IDLE, 2),
    ]

    first = llm.round_robin(workers)
    second = llm.round_robin(workers)
    third = llm.round_robin(workers)
    fourth = llm.round_robin(workers)

    assert [worker.name for worker in [first, second, third, fourth]] == [
        "worker-a",
        "worker-b",
        "worker-c",
        "worker-a",
    ]


def test_choose_worker_node_returns_none_for_empty_input():
    """An empty worker list should not produce a selection."""
    assert llm.choose_worker_node([]) is None


def test_choose_worker_node_prefers_idle_worker_by_name():
    """The selector should prefer idle workers and choose the first by name."""
    workers = [
        UnitTestWorkerNodes.make("worker-b", WorkerStatus.IDLE, 2, max_slots=4),
        UnitTestWorkerNodes.make("worker-a", WorkerStatus.IDLE, 1, max_slots=2),
        UnitTestWorkerNodes.make("worker-c", WorkerStatus.WORKING, 3, inflight_requests=2, max_slots=5),
    ]

    selected = llm.choose_worker_node(workers)

    assert selected is not None
    assert selected.name == "worker-a"


def test_choose_worker_node_picks_highest_free_slots():
    """If no worker is idle, choose the one with the most free capacity."""
    workers = [
        UnitTestWorkerNodes.make("worker-a", WorkerStatus.WORKING, 1, inflight_requests=2, max_slots=3),
        UnitTestWorkerNodes.make("worker-b", WorkerStatus.WORKING, 2, inflight_requests=1, max_slots=5),
        UnitTestWorkerNodes.make("worker-c", WorkerStatus.WORKING, 3, inflight_requests=4, max_slots=4),
    ]

    selected = llm.choose_worker_node(workers)

    assert selected is not None
    assert selected.name == "worker-b"


def test_choose_worker_node_ties_on_free_slots_choose_by_name():
    """When free slots tie, choose the first worker by name."""
    workers = [
        UnitTestWorkerNodes.make("worker-c", WorkerStatus.WORKING, 3, inflight_requests=1, max_slots=4),
        UnitTestWorkerNodes.make("worker-a", WorkerStatus.WORKING, 1, inflight_requests=1, max_slots=4),
        UnitTestWorkerNodes.make("worker-b", WorkerStatus.WORKING, 2, inflight_requests=1, max_slots=4),
    ]

    selected = llm.choose_worker_node(workers)

    assert selected is not None
    assert selected.name == "worker-a"


def test_choose_worker_node_round_robin_when_all_best_workers_are_full():
    """If every eligible worker is full, fall back to round-robin selection."""
    workers = [
        UnitTestWorkerNodes.make("worker-b", WorkerStatus.WORKING, 2, inflight_requests=3, max_slots=3),
        UnitTestWorkerNodes.make("worker-a", WorkerStatus.WORKING, 1, inflight_requests=2, max_slots=2),
        UnitTestWorkerNodes.make("worker-c", WorkerStatus.WORKING, 3, inflight_requests=5, max_slots=5),
    ]

    first = llm.choose_worker_node(workers)
    second = llm.choose_worker_node(workers)

    assert first is not None
    assert second is not None
    assert [first.name, second.name] == ["worker-a", "worker-b"]
