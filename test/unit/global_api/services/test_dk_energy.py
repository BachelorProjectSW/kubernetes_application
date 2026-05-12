from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.global_api.services.dk_energy import _ms_to_iso, get_dk_hourly


pytestmark = pytest.mark.unit


def test_ms_to_iso_converts_epoch_milliseconds_to_utc_string():
    """Epoch milliseconds should be turned into a readable UTC time."""
    assert _ms_to_iso(0) == "1970-01-01 00:00:00"


def test_get_dk_hourly_normalizes_timestamp_fields():
    """DK energy rows should expose `timestamp` instead of `timestamp_ms`."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = [
        {"timestamp_ms": 0, "consumption_w": 123.0, "generation_w": 45.0},
        {"timestamp_ms": 3600000, "consumption_w": 120.0, "generation_w": 50.0},
    ]

    with patch("src.global_api.services.dk_energy.requests.get", return_value=mock_response):
        result = get_dk_hourly(
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        )

    assert result == [
        {"timestamp": "1970-01-01 00:00:00", "consumption_w": 123.0, "generation_w": 45.0},
        {"timestamp": "1970-01-01 01:00:00", "consumption_w": 120.0, "generation_w": 50.0},
    ]
