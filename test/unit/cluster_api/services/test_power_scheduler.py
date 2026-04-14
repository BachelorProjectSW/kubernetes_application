import pytest
from src.cluster_api.services import power_scheduler as scheduler
from src.models.basemodels import WorkerNode
from src.models.enum import WorkerStatus


pytestmark = pytest.mark.unit


def _make_node(name: str, status: WorkerStatus, gpio: int) -> WorkerNode:
    """Generate a worker node."""
    return WorkerNode(name=name, ip="127.0.0.1", status=status, gpio=gpio)


@pytest.mark.unit
def test_select_nodes_to_turn_on_returns_off_nodes_up_to_requested_count():
    """Test select nodes to turn on."""
    nodes = [
        _make_node("n1", WorkerStatus.IDLE, 1),
        _make_node("n2", WorkerStatus.OFF, 2),
        _make_node("n3", WorkerStatus.OFF, 3),
        _make_node("n4", WorkerStatus.OFF, 4),
    ]

    selected = scheduler.select_nodes_to_turn_on(2, nodes)

    assert [node.name for node in selected] == ["n2", "n3"]


@pytest.mark.unit
def test_select_nodes_to_turn_off_returns_idle_nodes_up_to_requested_count():
    """Test nodes to turn off."""
    nodes = [
        _make_node("n1", WorkerStatus.WORKING, 1),
        _make_node("n2", WorkerStatus.IDLE, 2),
        _make_node("n3", WorkerStatus.IDLE, 3),
        _make_node("n4", WorkerStatus.IDLE, 4),
    ]

    selected = scheduler.select_nodes_to_turn_off(2, nodes)

    assert [node.name for node in selected] == ["n2", "n3"]
