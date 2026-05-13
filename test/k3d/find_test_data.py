from datetime import datetime, timedelta, timezone


# ============================================================
# CONSTRAINTS (YOUR NEW FORMAT)
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
# MAIN CLASS
# ============================================================
class TestDataFinder:

    def __init__(self, constraints):
        self.constraints = constraints

    # ------------------------------------------------------------
    # MOCK DATA (replace with real API calls)
    # ------------------------------------------------------------
    def _fetch_hour_data(self, t):
        # deterministic fake data so logic is testable
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
    # PRETTY PRINT DATA
    # ------------------------------------------------------------
    def _print_data(self, data):
        print("\n📊 DATA")
        for c, vals in data.items():
            print(f"\n{c}:")
            for k, v in vals.items():
                print(f"  {k}: {v}")

    # ------------------------------------------------------------
    # PRETTY PRINT CONSTRAINTS
    # ------------------------------------------------------------
    def _print_constraints(self, constraints):
        print("\n📌 CONSTRAINTS")
        for field, rule in constraints.items():
            print(f"  {field}: {rule}")

    # ------------------------------------------------------------
    # CORE CHECK
    # ------------------------------------------------------------
    def _check_field(self, cluster, field, value, rule):

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
    # CHECK ONE HOUR
    # ------------------------------------------------------------
    def _check_hour(self, t):

        print("\n" + "=" * 80)
        print(f"⏰ TIME: {t}")
        print("=" * 80)

        data = self._fetch_hour_data(t)

        self._print_data(data)

        # evaluate each cluster
        for cluster, rules in self.constraints.get(0, {}).items():

            print(f"\n📍 Cluster: {cluster}")

            cluster_data = data.get(cluster)
            if not cluster_data:
                print("❌ missing cluster data")
                return False

            self._print_constraints(rules)

            for field, rule in rules.items():

                value = cluster_data.get(field)

                if value is None:
                    print(f"❌ missing {cluster}.{field}")
                    return False

                if not self._check_field(cluster, field, value, rule):
                    return False

        return True

    # ------------------------------------------------------------
    # CHECK TIMELINE (ALL OFFSETS MUST PASS)
    # ------------------------------------------------------------
    def check(self, base_time):

        print("\n" + "#" * 80)
        print(f"BASE: {base_time}")
        print("#" * 80)

        for offset, constraints in self.constraints.items():

            t = base_time + timedelta(hours=offset)

            print("\n" + "-" * 80)
            print(f"OFFSET +{offset} → {t}")
            print("-" * 80)

            data = self._fetch_hour_data(t)

            self._print_data(data)

            for cluster, rules in constraints.items():

                print(f"\n📍 Cluster: {cluster}")

                cluster_data = data.get(cluster)

                if not cluster_data:
                    print("❌ missing cluster data")
                    return False

                self._print_constraints(rules)

                for field, rule in rules.items():

                    value = cluster_data.get(field)

                    if value is None:
                        print(f"❌ missing {cluster}.{field}")
                        return False

                    if not self._check_field(cluster, field, value, rule):
                        return False

            print("\n✅ HOUR PASSED")

        print("\n==============================")
        print("ALL HOURS PASSED")
        print("==============================")

        return True


# ============================================================
# RUN EXAMPLE
# ============================================================
if __name__ == "__main__":

    finder = TestDataFinder(CONSTRAINTS)

    result = finder.check(datetime(2026, 3, 25, tzinfo=timezone.utc))

    print("\nRESULT:", result)