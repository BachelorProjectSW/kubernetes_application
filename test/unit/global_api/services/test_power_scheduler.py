import pytest

from src.global_api.services import power_scheduler as scheduler
from src.models.basemodels import (
    ClusterConfig,
    ClusterInformation,
    QuestionConfig,
    WorkerNode,
)
from src.models.enum import WorkerStatus


def _make_node(name: str, status: WorkerStatus, gpio: int = 1) -> WorkerNode:
    """Generate a worker node."""
    return WorkerNode(name=name, ip="127.0.0.1", status=status, gpio=gpio)


def _make_cluster_info(name: str, worker_nodes: list[WorkerNode]) -> ClusterInformation:
    """Generate a cluster into."""
    return ClusterInformation(
        cluster_config=ClusterConfig(
            name=name,
            ip="127.0.0.1",
            port="8080",
            gpio_list=[1, 2, 3],
            simulated_country_code="DK",
            llama_service_port="8081",
        ),
        question_config=QuestionConfig(
            question="question",
            max_output_tokens=10,
        ),
        worker_nodes=worker_nodes,
    )


def test_get_current_active_nodes_counts_working_and_idle_nodes():
    """Test get current active nodes inclusive idle nodes."""
    clusters = [
        _make_cluster_info(
            "dk",
            [
                _make_node("dk-1", WorkerStatus.WORKING),
                _make_node("dk-2", WorkerStatus.IDLE),
                _make_node("dk-3", WorkerStatus.OFF),
            ],
        ),
        _make_cluster_info(
            "pt",
            [
                _make_node("pt-1", WorkerStatus.OFF),
                _make_node("pt-2", WorkerStatus.IDLE),
            ],
        ),
    ]

    assert scheduler.get_current_active_nodes(clusters) == 3


@pytest.mark.unit
def test_estimate_nodes_to_add_calculates_and_clamps_to_zero():
    """Test estimate nodes needed."""
    assert scheduler.estimate_nodes_to_add(
        avg_latency_per_node_ms=1000,
        max_latency_ms=250,
        current_active_nodes=1,
        current_rps=0.8,
    ) == 3

    assert scheduler.estimate_nodes_to_add(
        avg_latency_per_node_ms=1000,
        max_latency_ms=250,
        current_active_nodes=10,
        current_rps=0.8,
    ) == 0
