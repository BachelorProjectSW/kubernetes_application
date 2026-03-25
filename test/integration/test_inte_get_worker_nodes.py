import pytest
from global_api.services.get_all_worker_nodes import get_all_worker_nodes


@pytest.mark.integration
def test_get_worker_nodes():
    """Test its working while the kubernetes is deployed."""
    assert [
        {'name': 'k3d-devcluster-dk-agent-0'},
        {'name': 'k3d-devcluster-po-agent-0'}
    ] == get_all_worker_nodes()
