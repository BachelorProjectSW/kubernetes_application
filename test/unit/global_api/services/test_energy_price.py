import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from global_api.services.energy_price import fetch_price_data

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

    with patch("global_api.services.energy_price.requests.get", return_value=mock_response):
        result = fetch_price_data(
            start=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end=datetime(2026, 3, 2, tzinfo=timezone.utc),
            zone="PT",
        )

    assert len(result) == 2
    assert result[0][1] == 85.3
    assert result[1][1] == 79.1
    assert isinstance(result[0][0], datetime)
