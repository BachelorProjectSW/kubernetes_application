import pytest
from ...k3d.cluster_configs.test_config import get_test_config
import requests


@pytest.mark.integration
def test_add_test_to_queue_endpoint():
    """Test."""
    config = get_test_config()
    url = f"http://{config.strato.ip}:{config.strato.port}/add_test_to_queue"
    response = requests.post(url, json=config.model_dump())
    print(response)
    assert len(response) == 1
    assert response['test_config']['id'] == '123'
