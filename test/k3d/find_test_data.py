from datetime import datetime, timedelta, timezone

from src.custom_logging.logger import log

from src.global_api.services.price_and_carbon_intensity import (
    fetch_price_data,
    fetch_carbon_intensity,
)
from src.global_api.services.pv_power import get_power
from src.global_api.services.dk_energy import get_dk_hourly

CONSTRAINTS = {
    0: {
        "DK": {
            "generation": {"min": 500},
            "consumption": {"max": 300}
        },
        "NL": {
            "pv": {"max": 200},
        },
    },
    1: {
        "DK": {
            "generation": {"max": 50},
        },
        "NL": {
            "pv": {"min": 200},
        },
    },
}

PV_CAPACITY_W = 1500

START_DATE = datetime(2026, 3, 1, tzinfo=timezone.utc)

NUM_DAYS = 30


class TestDataFinder:
    """Test data finder."""

    def __init__(self, constraints: dict, pv_capacity_w: float = 10000):
        """Init."""
        self.constraints = constraints
        self.max_offset = max(constraints.keys())

        self.clusters = set()
        for c in constraints.values():
            self.clusters.update(c.keys())

        self.clusters = list(self.clusters)
        self.pv_capacity_w = pv_capacity_w

    def _metric_value(self, metric: str, cluster_data: dict):
        if metric == "pv":
            return cluster_data.get("pv_watts")
        if metric == "cost":
            return cluster_data.get("cost_eur_mwh")
        if metric in {"gco2", "carbon"}:
            return cluster_data.get("gco2_per_kwh")
        if metric == "generation":
            return cluster_data.get("generation")
        if metric == "consumption":
            return cluster_data.get("consumption")
        return cluster_data.get(metric)

    # ------------------------------------------------------------
    # SIMPLE HOURLY PRINT
    # ------------------------------------------------------------
    def _print_hour_summary(self, timestamp: datetime, clusters_data: dict):
        print("\n" + "=" * 70)
        print(f"Time: {timestamp.isoformat()}")
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
                print("        FAIL (below min)")
                return False

        if max_val is not None:
            print(f"        max   = {max_val}")
            if value > max_val:
                print("        FAIL (above max)")
                return False

        print("        PASS")
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

                for metric_name, bounds in rules.items():
                    min_val = bounds.get("min")
                    max_val = bounds.get("max")
                    value = self._metric_value(metric_name, cluster_data)

                    if value is None:
                        print(f"  Missing {cluster}.{metric_name}")
                        return False

                    if not self._check_value(
                        f"{cluster}.{metric_name}",
                        value,
                        min_val,
                        max_val,
                    ):
                        return False

            print("\nHOUR PASS")

        print("\n==============================")
        print("ALL HOURS PASSED")
        print("==============================")

        return True

    def find(self, start_date: datetime, num_days: int = 30):
        """Find loop."""
        print("\nSearching timeline...")

        current_date = start_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        for day in range(num_days):

            print(f"\nDAY {day + 1}: {current_date.date()}")

            for hour in range(24):

                base_time = current_date + timedelta(hours=hour)

                if self._check_timeline(base_time):

                    print("\nMATCH FOUND")

                    return {
                        "base_time": base_time.isoformat(),
                        "simulated_start_time": base_time.strftime("%d/%m/%Y %H:%M:%S")
                    }

            current_date += timedelta(days=1)

        print("\nNO MATCH FOUND")
        return None


def main():
    """Start function."""
    finder = TestDataFinder(CONSTRAINTS, PV_CAPACITY_W)

    log.info(
        "find_test_data.start",
        start_date=START_DATE.isoformat(),
        num_days=NUM_DAYS,
        clusters=list(finder.clusters),
    )

    result = finder.find(START_DATE, NUM_DAYS)

    if result:
        log.info("find_test_data.match_found", simulated_start_time=result["simulated_start_time"])
        print("\n====================")
        print("MATCH")
        print(result)
        print("====================")
    else:
        log.warning("find_test_data.no_match")
        print("No match")


if __name__ == "__main__":
    main()
