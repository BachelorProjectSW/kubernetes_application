import pytest
from datetime import datetime, timezone, timedelta
from global_api.services.price_and_carbon_intensity import fetch_carbon_intensity, fetch_price_data


@pytest.mark.integration
def test_fetch_price_data_pt():
    """Fetches real data from Electricity Maps and verifies the returned list."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=1)

    result = fetch_price_data(start=start, end=end, zone="PT")

    assert len(result) > 0
    assert isinstance(result[0][0], datetime)
    assert isinstance(result[0][1], float)


@pytest.mark.integration
def test_fetch_carbon_intensity_pt():
    """Fetches carbon intensity data from Electricity Maps and verifies the list."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=1)

    result = fetch_carbon_intensity(start=start, end=end, zone="PT")

    assert len(result) > 0
    assert isinstance(result[0][0], datetime)
    assert isinstance(result[0][1], int)


@pytest.mark.integration
def test_fetch_carbon_intensity_dk():
    """Fetches carbon intensity data from Electricity Maps and verifies the list."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=1)

    result = fetch_carbon_intensity(start=start, end=end, zone="DK-DK1")

    assert len(result) > 0
    assert isinstance(result[0][0], datetime)
    assert isinstance(result[0][1], int)
