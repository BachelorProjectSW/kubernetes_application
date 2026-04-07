import pytest
from ...k3d.cluster_configs.test_config import get_test_config
import requests


@pytest.mark.integration
def test_add_and_remove_test_to_queue_endpoint():
    """Test."""
    config = get_test_config()
    #add
    url = f"http://{config.strato.ip}:{config.strato.port}/add_test_to_queue"
    for i in range(3):
        config = get_test_config()
        config.id=i
        response = requests.post(url, json=config.model_dump()).json()
        assert len(response) == i
        assert response[i]['id'] == i
    

    #delete
    url = f"http://{config.strato.ip}:{config.strato.port}/delete_test_from_queue"
    assert response.json()[0]['id'] == 0
    assert len(response) == 3
    response = requests.delete(url, json={"config_id": "0"}).json()
    assert response[0]['id'] != 0
    assert response[0]['id'] == 1
    assert len(response) == 2
    response = requests.delete(url, json={"config_id": "1"}).json()
    response = requests.delete(url, json={"config_id": "1"}).json()
    assert len(response) == 0
    assert response == []




