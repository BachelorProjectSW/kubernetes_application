import pytest
from src.cluster_api.services import power_scheduler as scheduler
from src.models.basemodels import ClusterInformation, QuestionConfig, WorkerNode
from src.models.enum import WorkerStatus
from test.k3d.cluster_configs.test_config import get_test_config


pytestmark = pytest.mark.unit


def _make_node(name: str, status: WorkerStatus, gpio: int) -> WorkerNode:
    """Generate a worker node."""
    return WorkerNode(name=name, ip="127.0.0.1", status=status, gpio=gpio)


def _make_cluster_info(worker_nodes: list[WorkerNode], config_id: str = "test-config") -> ClusterInformation:
    """Generate cluster information for cluster API tests."""
    base = get_test_config()
    return ClusterInformation(
        config_id=config_id,
        cluster_config=base.clusters[0].model_copy(
            update={
                "name": "dk",
                "ip": "127.0.0.1",
                "port": "8080",
                "simulated_country_code": "DK",
            }
        ),
        question_config=QuestionConfig(question="question", max_output_tokens=10),
        worker_nodes=worker_nodes,
    )


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


@pytest.mark.unit
def test_turn_off_idle_nodes_stay_one_keeps_last_active_or_idle_node(monkeypatch):
    """stay_one should prevent the last active-or-idle node from being shut down."""
    cluster_info = _make_cluster_info(
        [
            _make_node("n1", WorkerStatus.IDLE, 1),
            _make_node("n2", WorkerStatus.OFF, 2),
        ]
    )

    monkeypatch.setattr(scheduler.config_store, "get", lambda: cluster_info)
    turn_off_calls = []
    monkeypatch.setattr(
        scheduler,
        "turn_off_node",
        lambda worker_node, cluster_name: turn_off_calls.append((worker_node.name, cluster_name)),
    )

    result = scheduler.turn_off_idle_nodes(20, stay_one=True)

    assert result == {
        "requested": 0,
        "status": "off",
        "node_changed": 0,
        "nodes": [],
    }
    assert turn_off_calls == []


@pytest.mark.unit
def test_turn_off_idle_nodes_turns_off_idle_node_without_stay_one(monkeypatch):
    """When stay_one is false, eligible idle nodes can still be turned off."""
    cluster_info = _make_cluster_info(
        [
            _make_node("n1", WorkerStatus.IDLE, 1),
            _make_node("n2", WorkerStatus.OFF, 2),
        ]
    )

    monkeypatch.setattr(scheduler.config_store, "get", lambda: cluster_info)
    monkeypatch.setattr(scheduler, "get_idle_time", lambda node_name, cluster_name: 999)
    turn_off_calls = []
    monkeypatch.setattr(
        scheduler,
        "turn_off_node",
        lambda worker_node, cluster_name: turn_off_calls.append((worker_node.name, cluster_name)) or True,
    )

    scheduler.turn_off_idle_nodes(20, stay_one=False)

    assert turn_off_calls == [("n1", "dk")]
