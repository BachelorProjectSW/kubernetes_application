import pytest

from global_api.services.scoring import choose_cluster


@pytest.mark.integration
def test_integration_scoring_chooses_correct_cluster():
    """Test that scoring works as intended and returns the cluster with the highest value."""
    clusters = [
        {
            "cluster": "dk-dk1",
            "renewable_output_w": 200,
            "cluster_load_w": 1000,
            "grid_carbon_intensity": 100,
            "grid_electricity_price": 0.12,
        },
        {
            "cluster": "pt",
            "renewable_output_w": 400,
            "cluster_load_w": 1000,
            "grid_carbon_intensity": 300,
            "grid_electricity_price": 0.14,
        },
    ]

    chosen_cluster = choose_cluster(clusters, 0.7, 0.3)
    assert chosen_cluster == clusters[0]
