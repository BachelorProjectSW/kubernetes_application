import pytest
from kubernetes.services.get_worker_nodes import get_worker_nodes


@pytest.mark.unit
def test_get_worker_nodes(mocker):
    """Test on historical data and not the API call"""
    # Mock get nodes api call
    get_nodes = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"hello"}
    assert get_worker_nodes() == {"name":"pantrum"}
