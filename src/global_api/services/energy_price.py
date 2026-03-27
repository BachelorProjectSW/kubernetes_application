import os
from datetime import datetime
import structlog
import requests
from dotenv import load_dotenv

log = structlog.getLogger()

load_dotenv()

BASE_URL = "https://api.electricitymaps.com/v4"


def _get_headers() -> dict:
    """Read the Electricity Maps API key from the environment and return the auth header.

    Returns:
        dict: Header dictionary with the auth-token key.

    Raises:
        RuntimeError: If ELECTRICITY_MAPS_API_KEY is not set in the environment.

    """
    api_key = os.getenv("ELECTRICITY_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("ELECTRICITY_MAPS_API_KEY is not set.")
    return {"auth-token": api_key}


def fetch_price_data(start: datetime, end: datetime, zone: str) -> list[tuple[datetime, float]]:
    """Fetch hourly day-ahead electricity prices from the Electricity Maps API.

    Args:
        start: Start of the time range (timezone-aware datetime).
        end:   End of the time range (timezone-aware datetime). Max 10 days after start.
        zone:  Electricity Maps zone identifier, e.g. "PT" or "DK-DK1".

    Returns:
        List of (timestamp, price) tuples where price is in EUR/MWh.

    Raises:
        RuntimeError:       If the API key is not set.
        requests.HTTPError: If the Electricity Maps API returns an error response.

    """
    log.info("Fetching prices", zone=zone, start=str(start), end=str(end))
    try:
        response = requests.get(
            f"{BASE_URL}/price-day-ahead/past-range",
            headers=_get_headers(),
            params={
                "zone": zone,
                "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "temporalGranularity": "hourly",
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        log.error("Electricity Maps API error", status=e.response.status_code, zone=zone)
        raise

    entries = response.json().get("data", [])
    log.info("Prices fetched", count=len(entries))

    return [
        (datetime.fromisoformat(e["datetime"]), e["value"])
        for e in entries
    ]
