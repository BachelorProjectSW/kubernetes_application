from pathlib import Path
import pytest
import global_api.util.cluster_connection as cluster_connection


def test_multi_cluster_request(monkeypatch):
    """Test endpoint from multiple clusters."""
    test_config_path = Path(__file__).parents[1] / "k3d" / "cluster_configs" / "test_clusters.yaml"

    # Patch CONFIG_PATH to the test_config
    monkeypatch.setattr(cluster_connection, "CONFIG_PATH", test_config_path)

    # Now after patch get the function as CONFIG_PATH is constant and read when imported.
    from global_api.services.handle_llm_request import handle_llm_request

    response = handle_llm_request("Describe kubernetes")

    content = response['choices'][0]['message']['content']

    assert response
    assert content
