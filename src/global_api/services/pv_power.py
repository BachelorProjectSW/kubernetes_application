import csv
from datetime import datetime, timezone
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "pv_all_countries_2025_2026Q1.csv"


def floor_to_hour(dt: datetime) -> datetime:
    """Floor datetime to hour to the csv can find the row."""
    return dt.replace(minute=0, second=0, microsecond=0)


def get_power_factor_by_time(start: datetime, end: datetime, country: str) -> list[tuple[datetime, float]]:
    """Return PT PV capacity factors between start and end (inclusive).

    Args:
        start: Earliest timestamp to include.
        end: Latest timestamp to include.
        country: Country to get PV power factors for.

    Returns:
        List of (timestamp, capacity_factor) tuples where capacity_factor is 0.0-1.0.

    """
    if country.startswith("DK").upper():
        country = "DK"

    results = []
    start = floor_to_hour(start)
    end = floor_to_hour(end)
    with DATA_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = datetime.strptime(row["Date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if start <= timestamp <= end:
                results.append((timestamp, float(row[country])))
            elif timestamp > end:
                break

    return results


def get_power(
    start: datetime, end: datetime, country: str, pv_capacity_w: float
) -> list[tuple[datetime, float]]:
    """Return available solar power at specified microgrid between start and end (inclusive).

    Args:
        start: Earliest timestamp to include.
        end: Latest timestamp to include.
        country: Country to get PV power for.
        pv_capacity_w: Installed PV capacity in watts.

    Returns:
        List of (timestamp, watts) tuples where watts is pv_capacity_w * capacity_factor.

    """
    results = []

    factors = get_power_factor_by_time(start, end, country)

    for timestamp, factor in factors:
        available_power = pv_capacity_w * factor
        results.append((timestamp, available_power))

    return results
