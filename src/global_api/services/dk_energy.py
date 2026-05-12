"""Fetch Denmark energy data from the AAU Orin proxy service.

This module provides a small wrapper around the Orin HTTP endpoint used by
the project. In simple terms, it returns how much power was used
(`consumption_w`) and produced (`generation_w`) during a time window.
"""

import structlog
import requests
from datetime import datetime, timezone

log = structlog.get_logger()

ORIN_BASE_URL = "http://100.74.156.93:5050"


def _ms_to_iso(ms: int) -> str:
    """Convert epoch milliseconds into a readable UTC time string.

    Args:
        ms: Timestamp in milliseconds since 1970-01-01 UTC.

    Returns:
        UTC datetime string in `YYYY-MM-DD HH:MM:SS` format.
    """
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_dk_hourly(start: datetime, end: datetime) -> list[dict]:
    """Return Denmark energy readings for a given time range.

    The response contains one entry per time bucket with two key energy values:
    power used (`consumption_w`) and power produced (`generation_w`).
    Timestamps are normalized into readable UTC strings.

    Args:
        start: Start of requested interval (timezone-aware datetime).
        end: End of requested interval (timezone-aware datetime).

    Returns:
        List of dicts, each with:
            - timestamp: Human-readable UTC time string.
            - consumption_w: Power usage value in watts.
            - generation_w: Power production value in watts.

    """
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    log.info("global_api.dk_energy.hourly_fetch_started", start=str(start), end=str(end))

    try:
        response = requests.get(
            f"{ORIN_BASE_URL}/energy/hourly",
            params={"start": start_ms, "end": end_ms},
            timeout=60,
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        log.error("global_api.dk_energy.api_error", status_code=e.response.status_code)
        raise
    except Exception:
        log.error("global_api.dk_energy.connection_error", base_url=ORIN_BASE_URL)
        raise

    data = response.json()
    for reading in data:
        reading["timestamp"] = _ms_to_iso(reading["timestamp_ms"])
        del reading["timestamp_ms"]
    log.info("global_api.dk_energy.hourly_fetch_succeeded", reading_count=len(data))
    return data
