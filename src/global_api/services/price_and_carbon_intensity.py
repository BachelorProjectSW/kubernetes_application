import os
from datetime import datetime
import structlog
import requests
from dotenv import load_dotenv

log = structlog.get_logger()

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
    log.debug("global_api.market.price_fetch_started", zone=zone, start=str(start), end=str(end))
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
            timeout=120,
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        log.error("global_api.market.price_fetch_api_error", status_code=e.response.status_code, zone=zone)
        raise

    except Exception:
        log.error("global_api.market.price_fetch_unexpected_error", zone=zone)
        raise

    entries = response.json().get("data", [])
    log.info("global_api.market.price_fetch_succeeded", entry_count=len(entries), zone=zone, data=entries)

    return [(datetime.fromisoformat(e["datetime"]), e["value"]) for e in entries]


def fetch_carbon_intensity(start: datetime, end: datetime, zone: str) -> list[tuple[datetime, int]]:
    """Fetch hourly direct carbon intensity from the Electricity Maps API.

    Args:
        start: Start of the time range (timezone-aware datetime).
        end: End of the time range (timezone-aware datetime).
        zone: Electricity Maps zone identifier, e.g. "PT" or "DK-DK1".

    Returns:
        List of (timestamp, gCO2eq_per_kwh) tuples.

    Raises:
        RuntimeError: If the API key is not set.
        requests.HTTPError: If the Electricity Maps API returns an error response.

    """
    log.debug("global_api.market.carbon_fetch_started", zone=zone, start=str(start), end=str(end))
    try:
        response = requests.get(
            f"{BASE_URL}/carbon-intensity/past-range",
            headers=_get_headers(),
            params={
                "zone": zone,
                "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "temporalGranularity": "hourly",
            },
            timeout=120,
        )
        response.raise_for_status()

    except requests.HTTPError as e:
        log.error("global_api.market.carbon_fetch_api_error", status_code=e.response.status_code, zone=zone)
        raise

    except Exception:
        log.error("global_api.market.carbon_fetch_unexpected_error", zone=zone)
        raise

    entries = response.json().get("data", [])
    log.debug("global_api.market.carbon_fetch_succeeded", entry_count=len(entries), zone=zone, data=entries)

    return [(datetime.fromisoformat(e["datetime"]), e["carbonIntensity"]) for e in entries]
