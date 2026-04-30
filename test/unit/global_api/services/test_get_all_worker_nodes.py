from unittest.mock import MagicMock

import pytest
import requests

from src.global_api.services.get_all_worker_nodes import get_all_worker_nodes
from test.k3d.cluster_configs.test_config import get_test_config


pytestmark = pytest.mark.unit


def test_get_all_worker_nodes_returns_empty_list_when_no_config(monkeypatch):
    """If no config has been stored, no worker nodes are returned."""
    monkeypatch.setattr("src.global_api.services.get_all_worker_nodes.config_store.get", lambda: None)

    assert get_all_worker_nodes() == []


def test_get_all_worker_nodes_combines_lists_from_all_clusters(monkeypatch):
    """Worker nodes from each cluster should be concatenated into one list."""
    config = get_test_config()
    payloads = {
        config.clusters[0].name: [{"name": "dk-1"}, {"name": "dk-2"}],
        config.clusters[1].name: [{"name": "pt-1"}],
    }

    monkeypatch.setattr("src.global_api.services.get_all_worker_nodes.config_store.get", lambda: config)
    monkeypatch.setattr("src.global_api.services.get_all_worker_nodes.config_store.get_clusters", lambda: config.clusters)

    def fake_get(url, timeout):
        response = MagicMock()
        response.raise_for_status.return_value = None
        cluster_name = "dk" if ":8073/" in url else "pt"
        response.json.return_value = payloads[cluster_name]
        return response

    monkeypatch.setattr("src.global_api.services.get_all_worker_nodes.requests.get", fake_get)

    assert get_all_worker_nodes() == [{"name": "dk-1"}, {"name": "dk-2"}, {"name": "pt-1"}]


def test_get_all_worker_nodes_skips_clusters_with_request_errors(monkeypatch):
    """Request failures should be ignored so other clusters still contribute."""
    config = get_test_config()

    monkeypatch.setattr("src.global_api.services.get_all_worker_nodes.config_store.get", lambda: config)
    monkeypatch.setattr("src.global_api.services.get_all_worker_nodes.config_store.get_clusters", lambda: config.clusters)

    def fake_get(url, timeout):
        if ":8073/" in url:
            raise requests.RequestException("boom")
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = [{"name": "pt-1"}]
        return response

    monkeypatch.setattr("src.global_api.services.get_all_worker_nodes.requests.get", fake_get)

    assert get_all_worker_nodes() == [{"name": "pt-1"}]
