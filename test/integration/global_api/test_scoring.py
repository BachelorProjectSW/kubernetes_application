import pytest

from src.global_api.services.scoring import choose_cluster
from ...k3d.cluster_configs.test_config import get_test_config


@pytest.mark.integration
def test_integration_scoring_chooses_correct_cluster():
    """Test that scoring works as intended and returns the cluster with the highest value."""
    config = get_test_config()

    cluster_energy_data = [
        {"renewable_output_w": 200, "cluster_load_w": 1000, "grid_carbon_intensity": 100,
         "grid_electricity_price": 0.12},
        {"renewable_output_w": 400, "cluster_load_w": 1000, "grid_carbon_intensity": 300,
         "grid_electricity_price": 0.14},
    ]

    chosen_cluster, _ = choose_cluster(config.clusters, cluster_energy_data, config.weights, config.energy)
    assert chosen_cluster == config.clusters[1]
