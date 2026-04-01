from unittest.mock import patch
from global_api.services.scoring import compute_carbon_blend, compute_grid_fraction
import pytest


@pytest.mark.unit
def test_compute_grid_fraction_succeeds():
    grid_fraction = compute_grid_fraction(200, 1000)

    assert grid_fraction == 0.8


@pytest.mark.unit
def test_compute_carbon_blend_succeeds():
    with patch("global_api.services.scoring.compute_grid_fraction") as mock_grid_fraction:
        mock_grid_fraction.return_value = 0.8

        result = compute_carbon_blend(200, 1000, 400)
        assert result == 320
