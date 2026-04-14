import pytest
from datetime import datetime, timezone
from src.global_api.services.dk_energy import get_dk_range


@pytest.mark.integration
def test_get_dk_range_returns_correct_format():
    """Verify that get_dk_range returns data with expected fields and types."""
    start = datetime(2025, 5, 13, tzinfo=timezone.utc)
    end = datetime(2025, 5, 13, 1, tzinfo=timezone.utc)

    result = get_dk_range(start, end)

    assert len(result) > 0

    reading = result[0]
    assert "timestamp" in reading
    assert "consumption_w" in reading
    assert "generation_w" in reading
    assert isinstance(reading["timestamp"], str)
    assert isinstance(reading["consumption_w"], float)
    assert isinstance(reading["generation_w"], float)