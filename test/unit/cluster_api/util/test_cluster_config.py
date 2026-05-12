import pytest

from src.cluster_api.util.cluster_config import ConfigStore
from test.k3d.cluster_configs.worker_nodes import UnitTestWorkerNodes
from src.models.enum import WorkerStatus


pytestmark = pytest.mark.unit


def test_assign_gpios_assigns_values():
    """Assigns GPIOs from cluster_config.gpio_list to worker nodes."""

    workers = [
        UnitTestWorkerNodes.make("n1", WorkerStatus.IDLE, 0),
        UnitTestWorkerNodes.make("n2", WorkerStatus.OFF, 0),
        UnitTestWorkerNodes.make("n3", WorkerStatus.OFF, 0),
        UnitTestWorkerNodes.make("n4", WorkerStatus.OFF, 0),
    ]

    cluster_info = UnitTestWorkerNodes.cluster_information(workers)
    cluster_info.cluster_config.gpio_list = [10, 11, 12, 13]

    store = ConfigStore()
    store.set(cluster_info)
    store.assign_gpios()

    assert [n.gpio for n in store.config.worker_nodes] == [10, 11, 12, 13]


def test_assign_gpios_mismatch_raises():
    """Raises when GPIO list length doesn't match worker count."""

    workers = UnitTestWorkerNodes.dk_workers()
    cluster_info = UnitTestWorkerNodes.cluster_information(workers)
    # Too few GPIOs
    cluster_info.cluster_config.gpio_list = [1]

    store = ConfigStore()
    store.set(cluster_info)

    with pytest.raises(ValueError):
        store.assign_gpios()


def test_assign_forwarded_ports_sets_ports_in_k3d():
    """Sets forwarded ports sequentially when k3d mode is enabled."""

    workers = [
        UnitTestWorkerNodes.make("a", WorkerStatus.IDLE, 0),
        UnitTestWorkerNodes.make("b", WorkerStatus.IDLE, 0),
        UnitTestWorkerNodes.make("c", WorkerStatus.IDLE, 0),
    ]

    cluster_info = UnitTestWorkerNodes.cluster_information(workers)
    # Ensure k3d mode and a numeric base port
    cluster_info.cluster_config.k3d = True
    cluster_info.cluster_config.llama_service_port = "9000"

    store = ConfigStore()
    store.set(cluster_info)
    store.assign_forwarded_ports()

    base = int(cluster_info.cluster_config.llama_service_port)
    ports = sorted([w.forwarded_port for w in store.config.worker_nodes])
    assert ports == [base + i for i in range(len(workers))]


def test_get_worker_nodes_dict_returns_dicts():
    """Returns list of worker node dicts with expected names."""

    workers = UnitTestWorkerNodes.dk_workers()
    cluster_info = UnitTestWorkerNodes.cluster_information(workers)

    store = ConfigStore()
    store.set(cluster_info)

    nodes = store.get_worker_nodes_dict()
    assert isinstance(nodes, list)
    assert all(isinstance(n, dict) for n in nodes)
    assert [n["name"] for n in nodes] == [w.name for w in store.config.worker_nodes]
