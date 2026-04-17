import pytest
import requests
from ...k3d.cluster_configs.test_config import get_test_config


@pytest.mark.integration
@pytest.mark.slow
def test_start_test():
    """Full end to end tests."""
    config = get_test_config()
    base_url = f"http://{config.strato.ip}:{config.strato.port}"

    response = requests.post(f"{base_url}/start_test", json=config.model_dump(), timeout=60)
    assert response.status_code == 200
    # TODO analyse output data!!!!
