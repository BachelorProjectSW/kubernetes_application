import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from src.global_api.services.price_and_carbon_intensity import (
    _get_headers,
    fetch_carbon_intensity,
    fetch_price_data,
)

FAKE_RESPONSE = {
    "zone": "PT",
    "data": [
        {"datetime": "2026-03-01T00:00:00.000Z", "value": 85.3, "unit": "EUR/MWh"},
        {"datetime": "2026-03-01T01:00:00.000Z", "value": 79.1, "unit": "EUR/MWh"},
    ],
    "temporalGranularity": "hourly",
}


@pytest.mark.unit
def test_fetch_price_data_returns_correct_tuples(monkeypatch):
    """Fetched entries are returned as (datetime, float) tuples."""
    monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.json.return_value = FAKE_RESPONSE
    mock_response.raise_for_status.return_value = None

    with patch("src.global_api.services.price_and_carbon_intensity.requests.get", return_value=mock_response):
        result = fetch_price_data(
            start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end=datetime(2026, 3, 2, tzinfo=timezone.utc),
            zone="PT",
        )

    assert len(result) == 2
    assert result[0][1] == 85.3
    assert result[1][1] == 79.1
    assert isinstance(result[0][0], datetime)


@pytest.mark.unit
def test_get_headers_reads_api_key_from_environment(monkeypatch):
    """The auth header should be derived from ELECTRICITY_MAPS_API_KEY."""
    monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "header-key")

    assert _get_headers() == {"auth-token": "header-key"}


@pytest.mark.unit
def test_get_headers_raises_when_api_key_is_missing(monkeypatch):
    """Missing API keys should fail fast."""
    monkeypatch.delenv("ELECTRICITY_MAPS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ELECTRICITY_MAPS_API_KEY is not set"):
        _get_headers()


@pytest.mark.unit
def test_fetch_carbon_intensity_returns_correct_tuples(monkeypatch):
    """Carbon intensity entries are returned as (datetime, int) tuples."""
    monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "zone": "PT",
        "data": [
            {"datetime": "2026-03-01T00:00:00.000Z", "carbonIntensity": 150},
            {"datetime": "2026-03-01T01:00:00.000Z", "carbonIntensity": 135},
        ],
    }
    mock_response.raise_for_status.return_value = None

    with patch("src.global_api.services.price_and_carbon_intensity.requests.get", return_value=mock_response):
        result = fetch_carbon_intensity(
            start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end=datetime(2026, 3, 2, tzinfo=timezone.utc),
            zone="PT",
        )

    assert len(result) == 2
    assert result[0][1] == 150
    assert result[1][1] == 135
    assert isinstance(result[0][0], datetime)
