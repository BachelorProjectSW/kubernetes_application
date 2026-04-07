import pytest

from global_api.services.scoring import choose_cluster
from ...k3d.cluster_configs.test_config import get_test_config

@pytest.mark.integration
def test_integration_scoring_chooses_correct_cluster():
    """Test that scoring works as intended and returns the cluster with the highest value."""
    config = get_test_config()

    chosen_cluster = choose_cluster(config.clusters, config.weights)
    assert chosen_cluster == config.clusters[0]
