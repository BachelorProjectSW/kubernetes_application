import pytest
from datetime import datetime
from global_api.services.carbon_intensity import get_carbon_intensity_by_time

@pytest.mark.integration
def test_get_carbon_intensity_by_time_reads_real_csv():
    """Test that get_carbon_intensity_by_time returns correct values from the actual CSV file."""
    result = get_carbon_intensity_by_time(datetime(2021, 1, 1, 0), datetime(2021, 1, 1, 2))

    assert result == [
        (datetime(2021, 1, 1, 0), 60.29),
        (datetime(2021, 1, 1, 1), 59.46),
        (datetime(2021, 1, 1, 2), 62.23),
    ]