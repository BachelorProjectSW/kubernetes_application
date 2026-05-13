import os
import sys
import json

from datetime import datetime, timedelta, timezone
from typing import Optional

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.global_api.services.price_and_carbon_intensity import (
    fetch_price_data,
    fetch_carbon_intensity,
)
from src.global_api.services.pv_power import get_power
from src.global_api.services.dk_energy import get_dk_hourly


# ============================================================================
# CONFIG
# ============================================================================

CONSTRAINTS = {
    "DK": {
        "generation_min": 500,
    },
    "ES": {
        "pv_watts_max": 500,
    },
    "PT": {
        "pv_watts_max": 1000,
    },
}

PV_CAPACITY_W = 10000

START_DATE = datetime(2026, 3, 25, tzinfo=timezone.utc)

NUM_DAYS = 30

# ============================================================================


class TestDataFinder:
    """Search for test hours matching multi-cluster constraints."""

    def __init__(
        self,
        constraints: dict,
        pv_capacity_w: float = 10000,
    ):
        self.constraints = constraints
        self.clusters = list(constraints.keys())
        self.pv_capacity_w = pv_capacity_w

    def _check_constraint(
        self,
        cluster: str,
        key: str,
        value: float,
        min_val: Optional[float],
        max_val: Optional[float],
    ) -> bool:

        print(f"      → Checking {cluster}.{key}")
        print(f"        value = {value}")

        if min_val is not None:
            print(f"        min   = {min_val}")
        if max_val is not None:
            print(f"        max   = {max_val}")

        if min_val is not None and value < min_val:
            print("        ❌ FAILED (below min)")
            return False

        if max_val is not None and value > max_val:
            print("        ❌ FAILED (above max)")
            return False

        print("        ✅ PASS")
        return True

    def _fetch_hour_data(self, hour_time: datetime) -> dict:
        """Fetch all cluster data for a single hour."""

        start = hour_time
        end = hour_time + timedelta(hours=1)

        data = {
            "timestamp": hour_time.isoformat(),
            "clusters": {},
        }

        for cluster in self.clusters:

            cluster_data = {}

            try:

                # Denmark special handling
                if cluster.upper().startswith("DK"):

                    dk_hourly = get_dk_hourly(start, end)

                    if dk_hourly:
                        entry = dk_hourly[0]

                        cluster_data["generation"] = entry.get("generation_w")
                        cluster_data["consumption"] = entry.get("consumption_w")

                else:

                    # Price
                    try:
                        prices = fetch_price_data(start, end, cluster)
                        if prices:
                            cluster_data["cost_eur_mwh"] = prices[0][1]
                    except Exception as e:
                        print(f"Warning price {cluster}: {e}")

                    # Carbon
                    try:
                        carbons = fetch_carbon_intensity(start, end, cluster)
                        if carbons:
                            cluster_data["gco2_per_kwh"] = carbons[0][1]
                    except Exception as e:
                        print(f"Warning carbon {cluster}: {e}")

                    # PV
                    try:
                        pv_data = get_power(
                            start,
                            end,
                            cluster,
                            self.pv_capacity_w,
                        )
                        if pv_data:
                            cluster_data["pv_watts"] = pv_data[0][1]
                    except Exception as e:
                        print(f"Warning PV {cluster}: {e}")

                data["clusters"][cluster] = cluster_data

            except Exception as e:
                print(f"Error cluster {cluster}: {e}")

        return data

    def _check_hour_constraints(self, data: dict) -> bool:
        """Check if all cluster constraints match."""

        if not data:
            return False

        clusters_data = data.get("clusters", {})

        for cluster, constraints in self.constraints.items():

            if cluster not in clusters_data:
                return False

            cluster_data = clusters_data[cluster]

            for constraint_key, constraint_value in constraints.items():

                if constraint_value is None:
                    continue

                if constraint_key.endswith("_min"):

                    value_key = constraint_key[:-4]

                    min_val = constraint_value
                    max_val = constraints.get(f"{value_key}_max")

                elif constraint_key.endswith("_max"):

                    value_key = constraint_key[:-4]

                    min_val = constraints.get(f"{value_key}_min")
                    max_val = constraint_value

                else:
                    continue

                value = cluster_data.get(value_key)

                if value is None:
                    print(f"      ⚠ Missing {cluster}.{value_key}")
                    return False

                if not self._check_constraint(
                    cluster=cluster,
                    key=value_key,
                    value=value,
                    min_val=min_val,
                    max_val=max_val,
                ):
                    return False

        return True

    def find(
        self,
        start_date: datetime,
        num_days: int = 30,
    ) -> Optional[dict]:
        """Search for a matching hour."""

        print("\nSearching for matching hour...")
        print(f"Clusters: {', '.join(self.clusters)}")

        current_date = start_date.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        for day_idx in range(num_days):

            print(
                f"\nDay {day_idx + 1}/{num_days}: "
                f"{current_date.strftime('%Y-%m-%d')}"
            )

            for hour in range(24):

                hour_time = current_date + timedelta(hours=hour)

                print(f"\nChecking {hour_time.strftime('%Y-%m-%d %H:%M')}")

                data = self._fetch_hour_data(hour_time)

                print("\n    Raw values:")
                for c, cd in data["clusters"].items():
                    print(f"      {c}: {cd}")

                if self._check_hour_constraints(data):

                    print("    ✅ MATCH FOUND")

                    data["simulated_start_time"] = hour_time.strftime(
                        "%d/%m/%Y %H:%M:%S"
                    )

                    return data

                print("    ❌ No match")

            current_date += timedelta(days=1)

        print(
            f"\nNo matching hour found in {num_days} days "
            f"({num_days * 24} hours)."
        )

        return None


def main():

    finder = TestDataFinder(
        constraints=CONSTRAINTS,
        pv_capacity_w=PV_CAPACITY_W,
    )

    result = finder.find(
        start_date=START_DATE,
        num_days=NUM_DAYS,
    )

    if result:

        print("\n" + "=" * 80)
        print(f"MATCHED HOUR: {result['timestamp']}")
        print("=" * 80)

        print("\nCluster Data:")

        for cluster, data in result["clusters"].items():

            print(f"\n{cluster}:")

            for key, value in data.items():

                if value is None:
                    continue

                if isinstance(value, float):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")

        with open("match_result.json", "w") as f:
            json.dump(result, f, indent=2)

        print("\nSaved result to match_result.json")

    else:
        print("\nNo matching data found.")
        sys.exit(1)


if __name__ == "__main__":
    main()