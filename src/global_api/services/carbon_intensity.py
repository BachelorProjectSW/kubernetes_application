import csv
from datetime import datetime
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data"


def _create_path(zone: str) -> Path:
    """Create a path to the carbon intensity data file for the given zone."""
    return DATA_PATH / f"carbon_intensity_{zone}_2021.csv"


def get_carbon_intensity_by_time(start: datetime, end: datetime, zone: str) -> list[tuple[datetime, float]]:
    """Return carbon intensity between start and end (inclusive).

    Args:
        start: Earliest timestamp to include.
        end: Latest timestamp to include.
        zone: The geographic zone for which to fetch carbon intensity data.


    Returns:
        List of (timestamp, carbon_intensity) tuples where carbon_intensity is in gCO2eq/kWh.

    """
    results = []

    zone = zone.lower()

    with open(_create_path(zone)) as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = datetime.strptime(row["time"], "%Y-%m-%dT%H:%M:%S.%f")
            if start <= timestamp <= end:
                carbon = float(row["Carbon intensity gCO₂eq/kWh (direct)"])
                results.append((timestamp, carbon))
            elif timestamp > end:
                break

    return results
