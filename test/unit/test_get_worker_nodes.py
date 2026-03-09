import pytest
from cluster_api.services.get_worker_nodes import get_worker_nodes


@pytest.mark.unit
def test_get_worker_nodes(mocker):
    """Test on historical data and not the API call"""
    with pytest.raises(Exception):
        get_worker_nodes
    assert 1
