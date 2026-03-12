import pytest
from cluster_api.services.get_worker_nodes import get_worker_nodes


@pytest.mark.integration
def test_get_worker_nodes():
    """Test its working while the kubernetes is deployed."""
    assert [
        {"name": "k3d-devcluster-agent-0"},
        {"name": "k3d-devcluster-agent-1"},
    ] == get_worker_nodes()
