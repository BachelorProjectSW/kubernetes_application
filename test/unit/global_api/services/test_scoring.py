from global_api.services.scoring import CARBON_REF_MAX, COST_REF_MAX, compute_grid_fraction
import pytest


@pytest.mark.unittest
def test_compute_grid_fraction_succeeds():
    grid_fraction = compute_grid_fraction(200, 1000)

    assert grid_fraction == 0.2
