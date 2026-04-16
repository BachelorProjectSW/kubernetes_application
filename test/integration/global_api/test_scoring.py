import pytest

from src.global_api.services.scoring import choose_cluster
from src.models.basemodels import ClusterRuntimeData
from ...k3d.cluster_configs.test_config import get_test_config


@pytest.mark.integration
def test_integration_scoring_chooses_correct_cluster():
    """Test that scoring uses runtime values and returns the highest-scoring cluster."""
    config = get_test_config()

    cluster_energy_data = [
        ClusterRuntimeData(renewable_output_w=200, cluster_load_w=1000, grid_carbon_intensity=100,
                           grid_electricity_price=0.12),
        ClusterRuntimeData(renewable_output_w=400, cluster_load_w=1000, grid_carbon_intensity=300,
                           grid_electricity_price=0.14),
    ]

    chosen_cluster, _ = choose_cluster(
        config.clusters, 
        cluster_energy_data, 
        config.weights, 
        config.energy, 
        config.latency.max_ms)
    assert chosen_cluster == config.clusters[1]
