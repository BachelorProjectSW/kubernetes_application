import pytest
from cluster_api.services.get_worker_nodes import get_worker_nodes


@pytest.mark.unit
def test_get_worker_nodes():
    """Test from a predownloaded get_worker_nodes file."""
    assert get_worker_nodes()
