import pytest
from cluster_api.services.get_worker_nodes import get_worker_nodes


@pytest.mark.unit
def test_get_worker_nodes():
    """Test on historical data and not the API call"""
    assert [{'name':'pantrum2'}] == get_worker_nodes()
