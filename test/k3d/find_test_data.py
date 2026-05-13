import os
import sys
import json

from datetime import datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.global_api.services.price_and_carbon_intensity import (
    fetch_price_data,
    fetch_carbon_intensity,
)
from src.global_api.services.pv_power import get_power
from src.global_api.services.dk_energy import get_dk_hourly


CONSTRAINTS = {
    0: {
        "DK": {
            "generation_min": 500,
            "consumption_max": 300
        },
        "PT": {
            "pv_watts_max": 100
        }
    },
    1: {
        "DK": {
            "generation_max": 100
        },
        "PT": {
            "pv_watts_min": 500
        }
    }
}

PV_CAPACITY_W = 1500

START_DATE = datetime(2026, 3, 25, tzinfo=timezone.utc)

NUM_DAYS = 30


class TestDataFinder:

    def __init__(self, constraints: dict, pv_capacity_w: float = 10000):
        self.constraints = constraints
        self.max_offset = max(constraints.keys())

        self.clusters = set()
        for c in constraints.values():
            self.clusters.update(c.keys())

        self.clusters = list(self.clusters)
        self.pv_capacity_w = pv_capacity_w

    # ------------------------------------------------------------
    # SIMPLE HOURLY PRINT
    # ------------------------------------------------------------
    def _print_hour_summary(self, timestamp: datetime, clusters_data: dict):
        print("\n" + "=" * 70)
        print(f"🕒 {timestamp.isoformat()}")
        print("=" * 70)

        for cluster, data in clusters_data.items():
            print(f"\n  {cluster}:")

            if cluster.upper().startswith("DK"):
                print(f"    generation   : {data.get('generation')}")
                print(f"    consumption  : {data.get('consumption')}")
            else:
                print(f"    price        : {data.get('cost_eur_mwh')}")
                print(f"    carbon       : {data.get('gco2_per_kwh')}")
                print(f"    pv           : {data.get('pv_watts')}")

    # ------------------------------------------------------------
    # FETCH DATA
    # ------------------------------------------------------------
    def _fetch_hour_data(self, hour_time: datetime) -> dict:

        start = hour_time
        end = hour_time + timedelta(hours=1)

        data = {
            "timestamp": hour_time.isoformat(),
            "clusters": {},
        }

        for cluster in self.clusters:

            cluster_data = {}

            if cluster.upper().startswith("DK"):

                dk_hourly = get_dk_hourly(start, end)

                if dk_hourly:
                    entry = dk_hourly[0]
                    cluster_data["generation"] = entry.get("avg_generation_w")
                    cluster_data["consumption"] = entry.get("avg_consumption_w")

            else:

                prices = fetch_price_data(start, end, cluster)
                if prices:
                    cluster_data["cost_eur_mwh"] = prices[0][1]

                carbons = fetch_carbon_intensity(start, end, cluster)
                if carbons:
                    cluster_data["gco2_per_kwh"] = carbons[0][1]

                pv_data = get_power(start, end, cluster, self.pv_capacity_w)
                if pv_data:
                    cluster_data["pv_watts"] = pv_data[0][1]

            data["clusters"][cluster] = cluster_data

        return data

    # ------------------------------------------------------------
    # SIMPLE AND CORRECT CONSTRAINT CHECKER
    # ------------------------------------------------------------
    def _check_value(self, name, value, min_val, max_val):

        print(f"      → Checking {name}")
        print(f"        value = {value}")

        if min_val is not None:
            print(f"        min   = {min_val}")
            if value < min_val:
                print("        ❌ FAIL (below min)")
                return False

        if max_val is not None:
            print(f"        max   = {max_val}")
            if value > max_val:
                print("        ❌ FAIL (above max)")
                return False

        print("        ✅ PASS")
        return True

    # ------------------------------------------------------------
    # TIMELINE CHECK
    # ------------------------------------------------------------
    def _check_timeline(self, base_time: datetime) -> bool:

        print("\n" + "#" * 70)
        print(f"BASE TIME: {base_time}")
        print("#" * 70)

        for offset, constraints in self.constraints.items():

            current_time = base_time + timedelta(hours=offset)

            print("\n" + "-" * 70)
            print(f"HOUR OFFSET {offset} → {current_time}")
            print("-" * 70)

            data = self._fetch_hour_data(current_time)
            clusters_data = data.get("clusters", {})

            self._print_hour_summary(current_time, clusters_data)

            for cluster, rules in constraints.items():

                print(f"\n  Checking cluster: {cluster}")

                if cluster not in clusters_data:
                    print("  ❌ Missing cluster data")
                    return False

                cluster_data = clusters_data[cluster]

                # ----------------------------------------------------
                # SIMPLE LOOP: CHECK EACH RULE DIRECTLY
                # ----------------------------------------------------
                for key, rule_value in rules.items():

                    if key.endswith("_min"):
                        value_key = key[:-4]
                        min_val = rule_value
                        max_val = rules.get(f"{value_key}_max")

                    elif key.endswith("_max"):
                        continue
                    else:
                        continue

                    value = cluster_data.get(value_key)

                    if value is None:
                        print(f"  ❌ Missing {value_key}")
                        return False

                    if not self._check_value(
                        f"{cluster}.{value_key}",
                        value,
                        min_val,
                        max_val,
                    ):
                        return False

            print("\n✅ HOUR PASS")

        print("\n==============================")
        print("ALL HOURS PASSED")
        print("==============================")

        return True

    # ------------------------------------------------------------
    # FIND LOOP
    # ------------------------------------------------------------
    def find(self, start_date: datetime, num_days: int = 30):

        print("\nSearching timeline...")

        current_date = start_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        for day in range(num_days):

            print(f"\nDAY {day + 1}: {current_date.date()}")

            for hour in range(24):

                base_time = current_date + timedelta(hours=hour)

                if self._check_timeline(base_time):

                    print("\n✅ MATCH FOUND")

                    return {
                        "base_time": base_time.isoformat(),
                        "simulated_start_time": base_time.strftime("%d/%m/%Y %H:%M:%S")
                    }

            current_date += timedelta(days=1)

        print("\n❌ NO MATCH FOUND")
        return None


def main():

    finder = TestDataFinder(CONSTRAINTS, PV_CAPACITY_W)

    result = finder.find(START_DATE, NUM_DAYS)

    if result:
        print("\n====================")
        print("MATCH")
        print(result)
        print("====================")
    else:
        print("No match")


if __name__ == "__main__":
    main()