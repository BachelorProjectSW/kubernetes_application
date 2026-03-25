import pytest
from datetime import datetime
from global_api.services.pv_power import get_pt_power_factor_by_time, get_pt_power, POWER_CAPACITY


@pytest.mark.integration
@pytest.mark.skipif(not DATA_FILE.exists(), reason="CSV data file not available")
def test_get_pt_power_factor_by_time_reads_real_csv():
    """Test that get_pt_power_factor_by_time returns correct values from the actual CSV file."""
    result = get_pt_power_factor_by_time(datetime(2010, 6, 1, 10), datetime(2010, 6, 1, 12))

    assert result == [
        (datetime(2010, 6, 1, 10), 0.6989),
        (datetime(2010, 6, 1, 11), 0.7994),
        (datetime(2010, 6, 1, 12), 0.8415),
    ]


@pytest.mark.integration
@pytest.mark.skipif(not DATA_FILE.exists(), reason="CSV data file not available")
def test_get_pt_power_reads_real_csv_and_calculates_power():
    """Test that get_pt_power returns correct available power from the actual CSV file."""
    result = get_pt_power(datetime(2010, 6, 1, 10), datetime(2010, 6, 1, 12))

    assert len(result) == 3
    assert result[0] == (datetime(2010, 6, 1, 10), POWER_CAPACITY * 0.6989)
    assert result[1] == (datetime(2010, 6, 1, 11), POWER_CAPACITY * 0.7994)
    assert result[2] == (datetime(2010, 6, 1, 12), POWER_CAPACITY * 0.8415)
