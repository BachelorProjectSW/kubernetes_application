import pytest

from src.models.enum import WorkerStatus
from test.k3d.cluster_configs.worker_nodes import UnitTestWorkerNodes


@pytest.mark.unit
def test_capacity_when_below_max_slots():
    """Below capacity: every inflight request is active, none queued."""
    node = UnitTestWorkerNodes.make(
        "n1", WorkerStatus.WORKING, 1, inflight_requests=2, max_slots=5
    )

    assert node.active_requests == 2
    assert node.queued_requests == 0
    assert node.free_slots == 3


@pytest.mark.unit
def test_capacity_when_exactly_at_max_slots():
    """At capacity: all slots active, nothing queued, no free slots."""
    node = UnitTestWorkerNodes.make(
        "n1", WorkerStatus.WORKING, 1, inflight_requests=4, max_slots=4
    )

    assert node.active_requests == 4
    assert node.queued_requests == 0
    assert node.free_slots == 0


@pytest.mark.unit
def test_capacity_when_over_max_slots_queues_overflow():
    """Over capacity: active caps at max_slots, the overflow becomes queue depth."""
    node = UnitTestWorkerNodes.make(
        "n1", WorkerStatus.WORKING, 1, inflight_requests=7, max_slots=4
    )

    assert node.active_requests == 4
    assert node.queued_requests == 3
    assert node.free_slots == 0


@pytest.mark.unit
def test_zero_max_slots_node_has_no_active_or_free_capacity():
    """An off node (max_slots=0) treats all inflight requests as queued."""
    node = UnitTestWorkerNodes.make(
        "n2", WorkerStatus.OFF, 2, inflight_requests=3, max_slots=0
    )

    assert node.active_requests == 0
    assert node.queued_requests == 3
    assert node.free_slots == 0


@pytest.mark.unit
def test_idle_node_defaults_are_empty():
    """A freshly made idle node reports no load and full free capacity."""
    node = UnitTestWorkerNodes.make("n1", WorkerStatus.IDLE, 1, max_slots=2)

    assert node.active_requests == 0
    assert node.queued_requests == 0
    assert node.free_slots == 2
