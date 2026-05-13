from datetime import datetime, timedelta, timezone


# ============================================================
# CONSTRAINTS (YOUR FORMAT)
# ============================================================
CONSTRAINTS = {
    0: {
        "DK": {
            "generation": {"min": 500, "max": 700},
            "consumption": {"max": 300}
        },
        "PT": {
            "pv": {"min": 100}
        }
    },
    1: {
        "DK": {
            "generation": {"max": 100}
        },
        "PT": {
            "pv": {"min": 500}
        }
    }
}


# ============================================================
# MAIN ENGINE
# ============================================================
class TestDataFinder:

    def __init__(self, constraints):
        self.constraints = constraints
        self.max_offset = max(constraints.keys())

    # ------------------------------------------------------------
    # MOCK DATA (replace with real APIs)
    # ------------------------------------------------------------
    def _fetch_hour_data(self, t: datetime):

        hour = t.hour

        return {
            "DK": {
                "generation": 650 if hour == 16 else 80,
                "consumption": 250
            },
            "PT": {
                "pv": 120 if hour == 16 else 600
            }
        }

    # ------------------------------------------------------------
    # PRINT DATA
    # ------------------------------------------------------------
    def _print_data(self, t, data):

        print("\n📊 DATA SNAPSHOT")
        print(f"TIME: {t}")

        for c, vals in data.items():
            print(f"\n{c}:")
            for k, v in vals.items():
                print(f"  {k}: {v}")

    # ------------------------------------------------------------
    # CHECK SINGLE VALUE
    # ------------------------------------------------------------
    def _check_value(self, cluster, field, value, rule):

        print(f"\n🧪 {cluster}.{field}")
        print(f"   value = {value}")

        min_v = rule.get("min")
        max_v = rule.get("max")

        if min_v is not None:
            print(f"   min   = {min_v}")
            if value < min_v:
                print("❌ FAIL (below min)")
                return False

        if max_v is not None:
            print(f"   max   = {max_v}")
            if value > max_v:
                print("❌ FAIL (above max)")
                return False

        print("✅ PASS")
        return True

    # ------------------------------------------------------------
    # CHECK ONE TIMELINE START
    # ------------------------------------------------------------
    def _check_timeline(self, base_time: datetime):

        print("\n" + "#" * 80)
        print(f"BASE TIME: {base_time}")
        print("#" * 80)

        # check ALL offsets
        for offset, constraints in self.constraints.items():

            t = base_time + timedelta(hours=offset)

            print("\n" + "-" * 80)
            print(f"OFFSET +{offset} → {t}")
            print("-" * 80)

            data = self._fetch_hour_data(t)

            self._print_data(t, data)

            # check each cluster
            for cluster, rules in constraints.items():

                print(f"\n📍 Cluster: {cluster}")

                cluster_data = data.get(cluster)

                if not cluster_data:
                    print("❌ missing cluster data")
                    return False

                for field, rule in rules.items():

                    value = cluster_data.get(field)

                    if value is None:
                        print(f"❌ missing {cluster}.{field}")
                        return False

                    if not self._check_value(cluster, field, value, rule):
                        return False

            print("\n✅ HOUR PASSED")

        print("\n==============================")
        print("ALL HOURS PASSED")
        print("==============================")

        return True

    # ------------------------------------------------------------
    # FULL SEARCH OVER DAYS + HOURS
    # ------------------------------------------------------------
    def find(self, start_date: datetime, num_days: int):

        print("\n🔍 STARTING SEARCH")
        print(f"Start date: {start_date}")
        print(f"Max offset: {self.max_offset} hours")

        base_day = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        for day in range(num_days):

            current_day = base_day + timedelta(days=day)

            print("\n" + "=" * 80)
            print(f"📅 DAY {day + 1}: {current_day.date()}")
            print("=" * 80)

            for hour in range(24):

                base_time = current_day + timedelta(hours=hour)

                print("\n" + "●" * 80)
                print(f"🧭 TESTING BASE TIME: {base_time}")
                print("●" * 80)

                if self._check_timeline(base_time):

                    print("\n🎯 MATCH FOUND")

                    return {
                        "base_time": base_time.isoformat(),
                        "simulated_start_time": base_time.strftime("%d/%m/%Y %H:%M:%S")
                    }

        print("\n❌ NO MATCH FOUND")
        return None


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":

    finder = TestDataFinder(CONSTRAINTS)

    result = finder.find(
        start_date=datetime(2026, 3, 25, tzinfo=timezone.utc),
        num_days=3
    )

    print("\nRESULT:", result)