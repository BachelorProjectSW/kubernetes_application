from cluster_api.configurer.configuration_request import ConfigModel, render_yaml
import httpx
from unittest.mock import patch, mock_open
from fastapi.testclient import TestClient
from src.cluster_api.configurer.configuration_request import app


def test_render_yaml():
    """Docstring jeg skriver senere."""
    # arrange
    fake_yaml = "name: {meta_name}\nreplicas: {replicas}"

    config = ConfigModel(
        experiment_id="exp5540",
        duration_minutes=5789,
        node_priority=["nano1", "nano2", "nano3"],
        start_time_replay="2026-03-16 11:49:09",
        request_rate=6789,
        latency_treshold=2001,
        scaling_interval=5,
        strategy_weights=["1", "2", "3", "4"]
        )

    # act
    with patch('builtins.open', mock_open(read_data=fake_yaml)):
        result = render_yaml("src/cluster_api/configurer/yaml_files/config.yaml", config)

    # assert
    assert "name: 5789" in result
    assert "replicas: 6789" in result



client = TestClient(app)

def test_configure_yaml_endpoint():
    # Arrange
    mock_configurations = {
        "experiment_id": "test-123",
        "duration_minutes": 5678,
        "node_priority": ["node1", "node2"],
        "start_time_replay": "2026-03-20 12:00:00",
        "request_rate": 8,
        "latency_treshold": 1008,
        "scaling_interval": 30,
        "strategy_weights": ["carbon emmision", "carbon price"]
    }


    with patch("src.cluster_api.configurer.configuration_request.render_yaml") as mock_render, \
         patch("src.cluster_api.configurer.configuration_request.save_config") as mock_save:


        mock_render.return_value = "fake: yaml_content"
    # Act
        response = client.post("/configure-yaml", json=mock_configurations)

    # Assert
    assert response.status_code == 200
    assert response.json() == {"hello": "world"}

    mock_render.assert_called_once()
    mock_save.assert_called_once_with("yaml_files/given_specs.yaml", "fake: yaml_content")
