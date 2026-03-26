from pathlib import Path
import pytest
import global_api.util.cluster_connection as cluster_connection


@pytest.mark.integration
def test_get_worker_nodes(monkeypatch):
    """Test to get all worker nodes using different cluster config such as ip addresses."""
    test_config_path = Path(__file__).parents[1] / "k3d" / "cluster_configs" / "test_clusters.yaml"

    # Patch CONFIG_PATH to the test_config
    monkeypatch.setattr(cluster_connection, "CONFIG_PATH", test_config_path)

    # Now after patch get the function as CONFIG_PATH is constant and read when imported.
    from global_api.services.get_all_worker_nodes import get_all_worker_nodes

    result = get_all_worker_nodes()

    assert result == [
        {'name': 'k3d-devcluster-dk-agent-0'},
        {'name': 'k3d-devcluster-po-agent-0'}
    ]
