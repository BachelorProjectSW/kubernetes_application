from unittest.mock import patch

import pytest
import requests

from src.global_api.services.get_all_worker_nodes import get_all_worker_nodes
from src.global_api.util.all_configuration import config_store
from src.models.enum import WorkerStatus
from test.k3d.cluster_configs.test_config import get_test_config
from test.k3d.cluster_configs.worker_nodes import UnitTestWorkerNodes


pytestmark = pytest.mark.unit


class _FakeResponse:
    """Minimal stand-in for requests.Response (no MagicMock)."""

    def __init__(self, payload):
        """Store the payload returned by ``json()``."""
        self._payload = payload

    def raise_for_status(self):
        """Succeed: the fixture only models healthy HTTP responses."""
        return None

    def json(self):
        """Return the canned payload."""
        return self._payload


@pytest.fixture(autouse=True)
def restore_config_store():
    """Snapshot and restore the module-global config store around each test."""
    original = config_store.get()
    yield
    config_store.set(original)


def test_aggregates_worker_nodes_from_all_clusters():
    """Nodes returned by every cluster API are concatenated into one list."""
    config_store.set(get_test_config())
    dk_nodes = UnitTestWorkerNodes.as_payload(UnitTestWorkerNodes.dk_workers())
    pt_nodes = UnitTestWorkerNodes.as_payload(
        [UnitTestWorkerNodes.make("pt1", WorkerStatus.IDLE, 1, max_slots=1)]
    )

    with patch(
        "src.global_api.services.get_all_worker_nodes.requests.get",
        side_effect=[_FakeResponse(dk_nodes), _FakeResponse(pt_nodes)],
    ):
        result = get_all_worker_nodes()

    assert len(result) == len(dk_nodes) + len(pt_nodes)
    assert {node["name"] for node in result} == {
        "n1", "n2", "n3", "n4", "pt1"
    }


def test_failing_cluster_does_not_lose_other_clusters_nodes():
    """A RequestException from one cluster still returns the reachable one."""
    config_store.set(get_test_config())
    dk_nodes = UnitTestWorkerNodes.as_payload(UnitTestWorkerNodes.dk_workers())

    with patch(
        "src.global_api.services.get_all_worker_nodes.requests.get",
        side_effect=[_FakeResponse(dk_nodes), requests.RequestException("pt down")],
    ):
        result = get_all_worker_nodes()

    assert [node["name"] for node in result] == ["n1", "n2", "n3", "n4"]


def test_non_list_payload_is_ignored():
    """A cluster returning a non-list payload contributes no nodes."""
    config_store.set(get_test_config())
    pt_nodes = UnitTestWorkerNodes.as_payload(
        [UnitTestWorkerNodes.make("pt1", WorkerStatus.IDLE, 1, max_slots=1)]
    )

    with patch(
        "src.global_api.services.get_all_worker_nodes.requests.get",
        side_effect=[_FakeResponse({"error": "unexpected"}), _FakeResponse(pt_nodes)],
    ):
        result = get_all_worker_nodes()

    assert [node["name"] for node in result] == ["pt1"]


def test_returns_empty_when_no_config_is_loaded():
    """With no active configuration the function short-circuits to an empty list."""
    config_store.set(None)

    assert get_all_worker_nodes() == []
