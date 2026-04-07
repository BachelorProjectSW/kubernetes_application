import pytest
from ...k3d.cluster_configs.test_config import get_test_config
import requests


@pytest.mark.integration
def test_add_test_to_queue_endpoint():
    """Test."""
    config = get_test_config()
    url = f"http://{config.strato.ip}:{config.strato.port}/add_test_to_queue"
    response = requests.post(url, json=config.model_dump())
    print(response.json())
    assert len(response.json()) == 1
    assert response.json()[0]['id'] == '123'

    config.id="123456"
    response = requests.post(url, json=config.model_dump())
    assert len(response.json()) == 2
    assert response.json()[0]['id'] == '123'
    assert response.json()[1]['id'] == '123456'
