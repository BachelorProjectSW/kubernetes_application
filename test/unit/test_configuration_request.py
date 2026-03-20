from cluster_api.configurer.configuration_request import ConfigModel, render_yaml
from unittest.mock import patch, mock_open


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
