from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.global_api.util.market_data_store import MarketDataStore


pytestmark = pytest.mark.unit

_START = datetime(2025, 6, 1, 12, tzinfo=timezone.utc)
_END = datetime(2025, 6, 1, 13, tzinfo=timezone.utc)

_DK_HOURLY = [{"timestamp": "2025-06-01 12:00:00", "consumption_w": 800.0, "generation_w": 350.0}]


@pytest.mark.unit
def test_get_power_uses_real_generation_for_dk_zone():
    """DK zones should return measured generation_w from the Orin proxy, not the CSV."""
    store = MarketDataStore()

    with patch("src.global_api.util.market_data_store.get_dk_hourly", return_value=_DK_HOURLY) as mock_dk:
        result = store.get_power(_START, _END, "DK-DK1", pv_capacity_w=1500.0)

    mock_dk.assert_called_once()
    assert result == [(datetime(2025, 6, 1, 12, tzinfo=timezone.utc), 350.0)]


@pytest.mark.unit
def test_get_power_uses_csv_for_non_dk_zone():
    """Non-DK zones should use the static CSV capacity-factor table."""
    store = MarketDataStore()
    csv_data = [(_START, 600.0)]

    with (
        patch("src.global_api.util.market_data_store.get_dk_hourly") as mock_dk,
        patch("src.global_api.util.market_data_store.get_power", return_value=csv_data) as mock_csv,
    ):
        result = store.get_power(_START, _END, "PT", pv_capacity_w=1500.0)

    mock_dk.assert_not_called()
    mock_csv.assert_called_once()
    assert result == csv_data


@pytest.mark.unit
def test_get_power_caches_dk_result():
    """A second call for the same DK zone within the TTL should not re-fetch."""
    store = MarketDataStore()

    with patch("src.global_api.util.market_data_store.get_dk_hourly", return_value=_DK_HOURLY) as mock_dk:
        store.get_power(_START, _END, "DK-DK1", pv_capacity_w=1500.0)
        store.get_power(_START, _END, "DK-DK1", pv_capacity_w=1500.0)

    assert mock_dk.call_count == 1
