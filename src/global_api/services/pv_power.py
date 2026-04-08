import csv
from datetime import datetime
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "PV_Utility_scale_no_tracking_RGB.csv"


def get_power_factor_by_time(start: datetime, end: datetime, country: str) -> list[tuple[datetime, float]]:
    """Return PT PV capacity factors between start and end (inclusive).

    Args:
        start: Earliest timestamp to include.
        end: Latest timestamp to include.
        country: Country to get PV power factors for.

    Returns:
        List of (timestamp, capacity_factor) tuples where capacity_factor is 0.0-1.0.

    """
    results = []

    with DATA_PATH.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = datetime.strptime(row["time"], "%Y-%m-%d %H:%M:%S")
            if start <= timestamp <= end:
                results.append((timestamp, float(row[country])))
            elif timestamp > end:
                break

    return results


def get_power(start: datetime, end: datetime, country: str, pv_capacity_w: float) -> list[tuple[datetime, float]]:
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
