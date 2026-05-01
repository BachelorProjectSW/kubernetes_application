from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.global_api.util.market_data_store import MarketDataStore


pytestmark = pytest.mark.unit

_START = datetime(2025, 6, 1, 12, tzinfo=timezone.utc)
_END = datetime(2025, 6, 1, 13, tzinfo=timezone.utc)
_NEXT_HOUR_START = datetime(2025, 6, 1, 13, tzinfo=timezone.utc)
_NEXT_HOUR_END = datetime(2025, 6, 1, 14, tzinfo=timezone.utc)

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
def test_get_power_caches_result_within_same_simulated_hour():
    """A second call for the same simulated hour should not re-fetch."""
    store = MarketDataStore()

    with patch("src.global_api.util.market_data_store.get_dk_hourly", return_value=_DK_HOURLY) as mock_dk:
        store.get_power(_START, _END, "DK-DK1", pv_capacity_w=1500.0)
        store.get_power(_START, _END, "DK-DK1", pv_capacity_w=1500.0)

    assert mock_dk.call_count == 1


@pytest.mark.unit
def test_get_power_refetches_on_new_simulated_hour():
    """Advancing to a new simulated hour should trigger a fresh fetch."""
    store = MarketDataStore()
    dk_next = [{"timestamp": "2025-06-01 13:00:00", "consumption_w": 750.0, "generation_w": 200.0}]

    with patch(
        "src.global_api.util.market_data_store.get_dk_hourly",
        side_effect=[_DK_HOURLY, dk_next],
    ) as mock_dk:
        store.get_power(_START, _END, "DK-DK1", pv_capacity_w=1500.0)
        store.get_power(_NEXT_HOUR_START, _NEXT_HOUR_END, "DK-DK1", pv_capacity_w=1500.0)

    assert mock_dk.call_count == 2


@pytest.mark.unit
def test_get_carbon_caches_within_same_simulated_hour():
    """Carbon data is not re-fetched for the same simulated hour."""
    store = MarketDataStore()
    carbon_data = [(_START, 120)]

    with patch(
        "src.global_api.util.market_data_store.fetch_carbon_intensity",
        return_value=carbon_data,
    ) as mock_carbon:
        store.get_carbon(_START, _END, "DK-DK1")
        store.get_carbon(_START, _END, "DK-DK1")

    assert mock_carbon.call_count == 1


@pytest.mark.unit
def test_get_carbon_refetches_on_new_simulated_hour():
    """Carbon data is re-fetched when simulated time crosses an hour boundary."""
    store = MarketDataStore()

    with patch(
        "src.global_api.util.market_data_store.fetch_carbon_intensity",
        return_value=[],
    ) as mock_carbon:
        store.get_carbon(_START, _END, "DK-DK1")
        store.get_carbon(_NEXT_HOUR_START, _NEXT_HOUR_END, "DK-DK1")

    assert mock_carbon.call_count == 2


@pytest.mark.unit
def test_get_price_caches_within_same_simulated_hour():
    """Price data is not re-fetched for the same simulated hour."""
    store = MarketDataStore()
    price_data = [(_START, 42.5)]

    with patch(
        "src.global_api.util.market_data_store.fetch_price_data",
        return_value=price_data,
    ) as mock_price:
        store.get_price(_START, _END, "DK-DK1")
        store.get_price(_START, _END, "DK-DK1")

    assert mock_price.call_count == 1


@pytest.mark.unit
def test_get_price_refetches_on_new_simulated_hour():
    """Price data is re-fetched when simulated time crosses an hour boundary."""
    store = MarketDataStore()

    with patch("src.global_api.util.market_data_store.fetch_price_data", return_value=[]) as mock_price:
        store.get_price(_START, _END, "DK-DK1")
        store.get_price(_NEXT_HOUR_START, _NEXT_HOUR_END, "DK-DK1")

    assert mock_price.call_count == 2
