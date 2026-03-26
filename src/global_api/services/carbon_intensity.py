import csv
from datetime import datetime
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "carbon_intensity_pt_2021.csv"

def get_carbon_intensity_by_time(start: datetime, end: datetime) -> list[tuple[datetime, float]]:
    """Return carbon intensity between start and end (inclusive).

    Args:
        start: Earliest timestamp to include.
        end: Latest timestamp to include.

    Returns:
        List of (timestamp, carbon_intensity) tuples where carbon_intensity is in gCO2eq/kWh.
    """
    results = []

    with open(DATA_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            timestamp = datetime.strptime(row["time"], "%Y-%m-%dT%H:%M:%S.%f")
            if start <= timestamp <= end:
                carbon = float(row["Carbon intensity gCO₂eq/kWh (direct)"])
                results.append((timestamp, carbon))
            elif timestamp > end:
                break

    return results