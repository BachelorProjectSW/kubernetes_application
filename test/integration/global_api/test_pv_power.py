import pytest
from datetime import datetime
from src.global_api.services.pv_power import get_power_factor_by_time, get_power
from src.models.basemodels import EnergyConfig


@pytest.mark.integration
def test_get_pt_power_factor_by_time_reads_real_csv():
    """Test that get_pt_power_factor_by_time returns correct values from the actual CSV file."""
    result = get_power_factor_by_time(datetime(2010, 6, 1, 10), datetime(2010, 6, 1, 12), "PT")

    assert result == [
        (datetime(2010, 6, 1, 10), 0.6989),
        (datetime(2010, 6, 1, 11), 0.7994),
        (datetime(2010, 6, 1, 12), 0.8415),
    ]


@pytest.mark.integration
def test_get_pt_power_reads_real_csv_and_calculates_power():
    """Test that get_pt_power returns correct available power from the actual CSV file."""
    pv_capacity_w = EnergyConfig().pv_capacity_w
    result = get_power(datetime(2010, 6, 1, 10), datetime(2010, 6, 1, 12), "PT", pv_capacity_w=pv_capacity_w)

    assert len(result) == 3
    assert result[0] == (datetime(2010, 6, 1, 10), pv_capacity_w * 0.6989)
    assert result[1] == (datetime(2010, 6, 1, 11), pv_capacity_w * 0.7994)
    assert result[2] == (datetime(2010, 6, 1, 12), pv_capacity_w * 0.8415)
