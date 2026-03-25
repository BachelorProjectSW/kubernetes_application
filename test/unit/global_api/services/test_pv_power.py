import pytest
from datetime import datetime
from unittest.mock import patch, mock_open
from global_api.services.pv_power import get_power_factor_by_time

CSV_CONTENT = """time,PT
2010-06-01 10:00:00,0.6989
2010-06-01 11:00:00,0.7994
2010-06-01 12:00:00,0.8415
2010-06-01 13:00:00,0.8368
"""


@pytest.mark.unit
def test_get_pt_power_returns_only_rows_within_range():
    """Only rows within start and end (inclusive) are returned."""
    with patch("pathlib.Path.open", mock_open(read_data=CSV_CONTENT)):
        result = get_power_factor_by_time(datetime(2010, 6, 1, 11), datetime(2010, 6, 1, 12), "PT")

    assert result == [
        (datetime(2010, 6, 1, 11), 0.7994),
        (datetime(2010, 6, 1, 12), 0.8415),
    ]


def test_get_pt_power_returns_empty_list_if_no_rows_within_range():
    """An empty list is returned if no rows are within start and end."""
    with patch("pathlib.Path.open", mock_open(read_data=CSV_CONTENT)):
        result = get_power_factor_by_time(datetime(2010, 6, 1, 14), datetime(2010, 6, 1, 15), "PT")

    assert result == []


@pytest.mark.unit
def test_get_pt_power_calculates_available_power():
    """Available power is capacity factor multiplied by max PV capacity."""
    with patch("pathlib.Path.open", mock_open(read_data=CSV_CONTENT)):
        with patch("global_api.services.pv_power.POWER_CAPACITY", 800):
            from global_api.services.pv_power import get_power
            result = get_power(datetime(2010, 6, 1, 11), datetime(2010, 6, 1, 12), "PT")

    assert len(result) == 2
    assert result[0] == (datetime(2010, 6, 1, 11), 800 * 0.7994)
    assert result[1] == (datetime(2010, 6, 1, 12), 800 * 0.8415)
