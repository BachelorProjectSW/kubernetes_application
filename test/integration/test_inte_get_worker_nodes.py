import pytest
from cluster_api.services.get_worker_nodes import get_all_nodes


@pytest.mark.integration
def test_get_worker_nodes():
    """Test its working while the kubernetes is deployed."""
    print(get_all_nodes())
    assert [
        {'name': 'k3d-devcluster-dk-agent-0'}, 
        {'name': 'k3d-devcluster-po-agent-0'}
    ] == get_all_nodes()
