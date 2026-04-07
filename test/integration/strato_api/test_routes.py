import pytest
import requests
from k3d.cluster_configs.test_config import get_test_config

@pytest.mark.integration
def test_add_and_remove_test_to_queue_endpoint():
    """Integration test for add/delete queue."""

    config = get_test_config()
    base_url = f"http://{config.strato.ip}:{config.strato.port}"

    # --- Add tests to queue ---
    for i in range(3):
        config = get_test_config()
        config.id = str(i)  # make sure id is a string to match Pydantic model
        response = requests.post(f"{base_url}/add_test_to_queue", json=config.model_dump()).json()
        print("Add response:", response)
        queue = response.get("queue", [])  # adjust depending on your actual response key
        assert len(queue) == i + 1
        assert queue[i]["id"] == str(i)

    # --- Delete tests from queue ---
    # Delete first item
    response = requests.delete(f"{base_url}/delete_test_from_queue", params={"config_id": "0"}).json()
    print("Delete response:", response)
    queue = response.get("queue", [])
    assert all(item["id"] != "0" for item in queue)
    assert len(queue) == 2

    # Delete second item
    response = requests.delete(f"{base_url}/delete_test_from_queue", params={"config_id": "1"}).json()
    queue = response.get("queue", [])
    assert all(item["id"] != "1" for item in queue)
    assert len(queue) == 1

    # Delete last item
    response = requests.delete(f"{base_url}/delete_test_from_queue", params={"config_id": "2"}).json()
    queue = response.get("queue", [])
    assert queue == []