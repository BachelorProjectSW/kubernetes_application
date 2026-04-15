import pytest
from datetime import datetime, timezone
from src.global_api.services.dk_energy import get_dk_hourly


@pytest.mark.integration
def test_get_dk_hourly_returns_correct_format():
    """Verify that get_dk_hourly returns data with expected fields and types."""
    start = datetime(2025, 5, 13, tzinfo=timezone.utc)
    end = datetime(2025, 5, 13, 1, tzinfo=timezone.utc)

    result = get_dk_hourly(start, end)

    assert len(result) > 0

    reading = result[0]
    assert "timestamp" in reading
    assert "avg_consumption_w" in reading
    assert "avg_generation_w" in reading
    assert isinstance(reading["timestamp"], str)
    assert isinstance(reading["avg_consumption_w"], float)
    assert isinstance(reading["avg_generation_w"], float)
