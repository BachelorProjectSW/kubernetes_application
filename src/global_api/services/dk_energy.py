"""Fetch Danish microgrid energy data from the AAU Orin proxy.

The Jetson Orin runs a Flask proxy on the microgrid network that
queries CrateDB and exposes the data over Tailscale. This module
calls that proxy to get consumption and generation data for the
Danish cluster.
"""

import structlog
import requests
from datetime import datetime, timezone

log = structlog.get_logger()

ORIN_BASE_URL = "http://100.72.251.69:5050"


def _ms_to_iso(ms: int) -> str:
    """Convert milliseconds since epoch to ISO format string."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_dk_latest() -> dict:
    """Return the most recent energy reading from the AAU microgrid.

    Returns:
        Dict with:
            - timestamp: Human-readable UTC string (str).
            - consumption_w: Microgrid local power consumption in watts (float).
            - generation_w: Microgrid renewable power generation in watts (float).

    """
    try:
        response = requests.get(
            f"{ORIN_BASE_URL}/energy/latest",
            timeout=10,
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        log.error("dk_energy.api_error", status=e.response.status_code)
        raise
    except Exception:
        log.error("dk_energy.connection_error", url=ORIN_BASE_URL)
        raise

    data = response.json()
    data["timestamp"] = _ms_to_iso(data["timestamp_ms"])
    del data["timestamp_ms"]
    log.info(
        "dk_energy.latest",
        consumption_w=data["consumption_w"],
        generation_w=data["generation_w"],
    )
    return data


def get_dk_hourly(start: datetime, end: datetime) -> list[dict]:
    """Return hourly averaged energy readings from the AAU microgrid.

    Args:
        start: Start of the time range (timezone-aware datetime).
        end: End of the time range (timezone-aware datetime).

    Returns:
        List of dicts, each with:
            - timestamp: Human-readable UTC string (str).
            - avg_consumption_w: Hourly average consumption in watts (float).
            - avg_generation_w: Hourly average generation in watts (float).

    """
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    log.info("dk_energy.fetching_hourly", start=str(start), end=str(end))

    try:
        response = requests.get(
            f"{ORIN_BASE_URL}/energy/hourly",
            params={"start": start_ms, "end": end_ms},
            timeout=15,
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        log.error("dk_energy.api_error", status=e.response.status_code)
        raise
    except Exception:
        log.error("dk_energy.connection_error", url=ORIN_BASE_URL)
        raise

    data = response.json()
    for reading in data:
        reading["timestamp"] = _ms_to_iso(reading["timestamp_ms"])
        del reading["timestamp_ms"]
    log.info("dk_energy.hourly_fetched", count=len(data))
    return data


def get_dk_range(start: datetime, end: datetime, limit: int = 1000) -> list[dict]:
    """Return energy readings from the AAU microgrid for a given time range.

    Args:
        start: Start of the time range (timezone-aware datetime).
        end: End of the time range (timezone-aware datetime).
        limit: Maximum number of readings to return.
    Returns:
       List of dicts, each with:
            - timestamp: Human-readable UTC string (str).
            - consumption_w: Power consumption in watts (float).
            - generation_w: Power generation in watts (float).

    """
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    log.info("dk_energy.fetching_range", start=str(start), end=str(end))

    try:
        response = requests.get(
            f"{ORIN_BASE_URL}/energy/range",
            params={"start": start_ms, "end": end_ms, "limit": limit},
            timeout=15,
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        log.error("dk_energy.api_error", status=e.response.status_code)
        raise
    except Exception:
        log.error("dk_energy.connection_error", url=ORIN_BASE_URL)
        raise

    data = response.json()
    for reading in data:
        reading["timestamp"] = _ms_to_iso(reading["timestamp_ms"])
        del reading["timestamp_ms"]
    log.info("dk_energy.range_fetched", count=len(data))
    return data
