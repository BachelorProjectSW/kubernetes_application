import pytest
from datetime import datetime, timezone
from src.global_api.services.pv_power import get_power_factor_by_time, get_power
from src.models.basemodels import EnergyConfig


def dt(hour):
    """Return a timezone-aware datetime on 2010-06-01 at the given hour."""
    return datetime(2010, 6, 1, hour, tzinfo=timezone.utc)


@pytest.mark.integration
def test_get_pt_power_factor_by_time_reads_real_csv():
    """Test that get_pt_power_factor_by_time returns correct values from the actual CSV file."""
    result = get_power_factor_by_time(dt(10), dt(12), "PT")

    assert result == [
        (dt(10), 0.6989),
        (dt(11), 0.7994),
        (dt(12), 0.8415),
    ]


@pytest.mark.integration
def test_get_pt_power_reads_real_csv_and_calculates_power():
    """Test that get_pt_power returns correct available power from the actual CSV file."""
    pv_capacity_w = EnergyConfig().pv_capacity_w
    result = get_power(dt(10), dt(12), "PT", pv_capacity_w=pv_capacity_w)

    assert len(result) == 3
    assert result[0] == (dt(10), pv_capacity_w * 0.6989)
    assert result[1] == (dt(11), pv_capacity_w * 0.7994)
    assert result[2] == (dt(12), pv_capacity_w * 0.8415)
