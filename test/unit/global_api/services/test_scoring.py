from unittest.mock import patch
from src.global_api.services.scoring import (
    compute_carbon_blend,
    compute_cost_blend,
    compute_grid_fraction,
    normalize_value,
    score_cluster,
)
import pytest


@pytest.mark.unit
def test_compute_grid_fraction_succeeds():
    """Test that compute grid fraction works."""
    grid_fraction = compute_grid_fraction(200, 1000)

    assert grid_fraction == 0.8


@pytest.mark.unit
def test_compute_carbon_blend_succeeds():
    """Test that compute carbon blend works."""
    with patch("global_api.services.scoring.compute_grid_fraction") as mock_grid_fraction:
        mock_grid_fraction.return_value = 0.8

        result = compute_carbon_blend(200, 1000, 400)
        assert result == 320


@pytest.mark.unit
def test_compute_cost_blend_succeeds():
    """Test that compute cost blend works."""
    with patch("global_api.services.scoring.compute_grid_fraction") as mock_grid_fraction:
        mock_grid_fraction.return_value = 0.8

        result = compute_cost_blend(200, 1000, 0.2)
        assert result == 0.16


@pytest.mark.unit
def test_normalize_value_succeeds():
    """Test that normalize value works."""
    result = normalize_value(80, 100)
    assert result == 0.2


@pytest.mark.unit
def test_score_cluster():
    """Test that score cluster works."""
    with (
        patch("global_api.services.scoring.compute_carbon_blend") as mock_carbon,
        patch("global_api.services.scoring.compute_cost_blend") as mock_cost,
        patch("global_api.services.scoring.normalize_value") as mock_normalize,
    ):
        mock_carbon.return_value = 200
        mock_cost.return_value = 0.5
        mock_normalize.side_effect = [0.4, 0.6]

        result = score_cluster(
            renewable_output_w=500,
            cluster_load_w=1000,
            grid_carbon_intensity=300,
            grid_electricity_price=0.2,
            carbon_weight=0.7,
            cost_weight=0.3,
        )

        assert result == 0.46
        mock_carbon.assert_called_once_with(500, 1000, 300)
        mock_cost.assert_called_once_with(500, 1000, 0.2)
