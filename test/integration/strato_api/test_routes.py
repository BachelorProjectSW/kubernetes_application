import pytest
import requests
from ...k3d.cluster_configs.test_config import get_test_config


@pytest.mark.integration
@pytest.mark.slow
def test_start_test():
    """Full end to end tests."""
    config = get_test_config()
    base_url = f"http://{config.strato.ip}:{config.strato.port}"

    response = requests.post(f"{base_url}/start_test", json=config.model_dump())
    assert response.status_code == 200
    # TODO analyse output data!!!!


@pytest.mark.integration
def test_add_and_remove_test_to_queue_endpoint():
    """Integration test for add/delete queue."""
    config = get_test_config()
    base_url = f"http://{config.strato.ip}:{config.strato.port}"

    # Add
    for i in range(3):
        config = get_test_config()
        config.id = str(i)  # id must be string to match Pydantic model
        response = requests.post(f"{base_url}/add_test_to_queue", json=config.model_dump()).json()
        assert len(response) == i + 1
        assert response[i]["id"] == str(i)

    # Delete first item
    response = requests.delete(f"{base_url}/delete_test_from_queue", params={"config_id": "0"}).json()
    assert all(item["id"] != "0" for item in response)
    assert len(response) == 2

    # Delete fake item
    response = requests.delete(f"{base_url}/delete_test_from_queue", params={"config_id": "999"}).json()
    assert len(response) == 2

    # Delete second item
    response = requests.delete(f"{base_url}/delete_test_from_queue", params={"config_id": "1"}).json()
    assert all(item["id"] != "1" for item in response)
    assert len(response) == 1

    # Delete last item
    response = requests.delete(f"{base_url}/delete_test_from_queue", params={"config_id": "2"}).json()
    assert response == []
