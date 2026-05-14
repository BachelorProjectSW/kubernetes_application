from __future__ import annotations

import time
from typing import Callable

import pytest
import requests
import os

from src.models.basemodels import Config
from test.k3d.cluster_configs.test_config import get_test_config


class K3dTestRunner:
    """Start a test, wait for completion, fetch the raw summary, and run assertions."""

    def __init__(self, config: Config, api_url: str = "http://127.0.0.1:8071"):
        """Init K3dTestRunner."""
        self.config = config
        self.api_url = api_url
        self.assertions: list[tuple[str, Callable[[dict], None]]] = []
        print(f"[INIT] {config.name}")

    def assert_total_requests(self, min_count: int | None = None, max_count: int | None = None):
        """Assert the total request count."""

        def check(summary: dict) -> None:
            count = summary.get("request_count", 0)
            if min_count is not None and count < min_count:
                raise AssertionError(f"Expected at least {min_count} requests, got {count}")
            if max_count is not None and count > max_count:
                raise AssertionError(f"Expected at most {max_count} requests, got {count}")

        self.assertions.append((f"total_requests({min_count}, {max_count})", check))
        return self

    def assert_success_rate(self, min_rate: float = 0.95):
        """Assert the global success rate."""

        def check(summary: dict) -> None:
            total_requests = summary.get("request_count", 0)
            successful_requests = summary.get("successful_requests", 0)
            if total_requests == 0:
                raise AssertionError("No requests executed")
            success_rate = successful_requests / total_requests
            if success_rate < min_rate:
                raise AssertionError(f"Success rate {success_rate:.2%} below minimum {min_rate:.2%}")

        self.assertions.append((f"success_rate(min={min_rate})", check))
        return self

    def assert_cluster_requests(
            self,
            cluster_name: str,
            min_count: int | None = None,
            max_count: int | None = None
        ):
        """Assert request count for one cluster."""

        def check(summary: dict) -> None:
            cluster_distribution = summary.get("cluster_distribution", {})
            count = cluster_distribution.get(cluster_name, 0)
            if min_count is not None and count < min_count:
                raise AssertionError(
                    f"Cluster {cluster_name}: expected at least {min_count} requests, got {count}"
                )
            if max_count is not None and count > max_count:
                raise AssertionError(
                    f"Cluster {cluster_name}: expected at most {max_count} requests, got {count}"
                )

        self.assertions.append((f"cluster_requests({cluster_name}, {min_count}, {max_count})", check))
        return self

    def assert_global_carbon(self, min_gco2: float | None = None, max_gco2: float | None = None):
        """Assert the global carbon total from the raw summary."""

        def check(summary: dict) -> None:
            value = float(summary.get("total_gco2_g", 0.0))
            if max_gco2 is not None and value > max_gco2:
                raise AssertionError(f"Global carbon {value:.2f} > {max_gco2}")
            if min_gco2 is not None and value < min_gco2:
                raise AssertionError(f"Global carbon {value:.2f} < {min_gco2}")

        self.assertions.append((f"global_carbon(max={max_gco2})", check))
        return self

    def assert_total_cost(self, min_eur: float | None = None, max_eur: float | None = None):
        """Assert the total cost (total_cost_eur) from the raw summary."""

        def check(summary: dict) -> None:
            value = float(summary.get("total_cost_eur", 0.0))
            if min_eur is not None and value < min_eur:
                raise AssertionError(f"Total cost {value:.6f} EUR < {min_eur}")
            if max_eur is not None and value > max_eur:
                raise AssertionError(f"Total cost {value:.6f} EUR > {max_eur}")

        self.assertions.append((f"total_cost({min_eur}, {max_eur})", check))
        return self

    def assert_avg_latency(self, min_ms: float | None = None, max_ms: float | None = None):
        """Assert the average latency across all requests."""

        def check(summary: dict) -> None:
            value = float(summary.get("avg_latency_ms", 0.0))
            if min_ms is not None and value < min_ms:
                raise AssertionError(f"Average latency {value:.1f}ms < {min_ms}")
            if max_ms is not None and value > max_ms:
                raise AssertionError(f"Average latency {value:.1f}ms > {max_ms}")

        self.assertions.append((f"avg_latency({min_ms}, {max_ms})", check))
        return self

    def assert_which_cluster_is_asserted(
        self,
        cluster_list: list[str],
        start_index: int | None = None,
        end_index: int | None = None,
        max_errors: int = 0,
    ):
        """Assert request routing order."""

        def check(summary: dict) -> None:
            requests = summary.get("request_over_time", [])

            if not requests:
                raise AssertionError("No request_over_time data available")

            if start_index is not None:
                requests = requests[start_index:]

            if end_index is not None:
                requests = requests[:end_index]

            if len(requests) != len(cluster_list):
                raise AssertionError(
                    f"Length mismatch: got {len(requests)} requests "
                    f"but expected {len(cluster_list)} clusters"
                )

            errors = 0

            for i, (request, expected_cluster) in enumerate(zip(requests, cluster_list)):
                actual_cluster = request["cluster"]

                print(
                    f"[{i}] expected={expected_cluster} "
                    f"actual={actual_cluster}"
                )

                if actual_cluster != expected_cluster:
                    errors += 1

                    if errors > max_errors:
                        raise AssertionError(
                            f"Too many cluster mismatches. "
                            f"Index={i}, expected={expected_cluster}, "
                            f"actual={actual_cluster}, "
                            f"errors={errors}, allowed={max_errors}"
                        )

        self.assertions.append(
            ("check request cluster order", check)
        )

        return self

    def _start_test(self) -> str:
        print(f"[START] POST {self.api_url}/start_test")
        response = requests.post(
            f"{self.api_url}/start_test",
            json=self.config.model_dump(),
            timeout=30,
        )
        response.raise_for_status()
        print(f"[START] config_name={self.config.name}")
        return self.config.name

    def _find_config_id_by_name(self, config_name: str, timeout_s: int = 60) -> str:
        print(f"[LOOKUP] waiting for config_name={config_name}")
        started_at = time.time()
        while time.time() - started_at < timeout_s:
            response = requests.get(f"{self.api_url}/get_configs", timeout=30)
            response.raise_for_status()
            for entry in response.json():
                if entry.get("config_name") == config_name:
                    config_id = entry.get("config_id") or entry.get("config_json", {}).get("id")
                    if config_id:
                        print(f"[LOOKUP] config_id={config_id}")
                        return config_id
            time.sleep(2)
        raise TimeoutError(f"Could not find config_id for '{config_name}' within {timeout_s} seconds")

    def _wait_for_completion(
            self,
            test_duration: int,
            time_buffer: int = 200,
            poll_interval_s: int = 10
        ) -> None:
        total_wait_time = test_duration + time_buffer
        print(f"[WAIT] waiting up to {total_wait_time}s")
        started_at = time.time()
        while time.time() - started_at < total_wait_time:
            response = requests.get(f"{self.api_url}/test_status", timeout=30)
            response.raise_for_status()
            status = response.json().get("status", "unknown")
            if status == "idle":
                print(f"[DONE] completed in {time.time() - started_at:.1f}s")
                return
            time.sleep(poll_interval_s)
        raise TimeoutError(f"Test did not complete within {total_wait_time} seconds")

    def _fetch_summary(self, config_id: str) -> dict:
        print(f"[FETCH] GET {self.api_url}/test_results?config_id={config_id}")
        response = requests.get(
            f"{self.api_url}/test_results",
            params={"config_id": config_id},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _run_assertions(self, summary: dict) -> None:
        print(f"[ASSERT] running {len(self.assertions)} assertions")
        for name, check in self.assertions:
            check(summary)
            print(f"  [OK] {name}")

    def _print_summary(self, summary: dict) -> None:
        print(f"\n{'=' * 72}")
        print(f"[PASS] {summary.get('test_name', self.config.name)} ({summary.get('config_id', 'unknown')})")
        print(
            f"requests={summary.get('request_count', 0)} "
            f"success={summary.get('successful_requests', 0)} "
            f"failure={summary.get('failed_requests', 0)}"
        )
        print(f"global carbon={summary.get('total_gco2_g', 0.0)}")
        print(f"global cost={summary.get('total_cost_eur', 0.0)}")
        print(f"cluster_distribution={summary.get('cluster_distribution', {})}")
        print(f"{'=' * 72}\n")

    def run(self, test_duration: int) -> dict:
        """Run the tests and wait for x seconds to abort."""
        config_name = self._start_test()
        self._wait_for_completion(test_duration=test_duration)
        time.sleep(10)  # ensure tests results is in db.
        config_id = self._find_config_id_by_name(config_name)
        summary = self._fetch_summary(config_id)
        self._run_assertions(summary)
        self._print_summary(summary)
        return summary


@pytest.mark.integration
def test_k3d_default():
    """Balanced default scenario."""
    config = get_test_config()
    (
        K3dTestRunner(config)
        .assert_total_requests(min_count=3, max_count=3)
        .assert_success_rate(min_rate=1)
        .run(config.start.duration_time_s)
    )


@pytest.mark.integration
def test_k3d_high_load():
    """Higher request-rate scenario."""
    config = get_test_config()
    config.workload.request_per_minute = 20

    (
        K3dTestRunner(config)
        .assert_total_requests(min_count=20, max_count=20)
        .assert_success_rate(min_rate=1)
        .run(config.start.duration_time_s)
    )


@pytest.mark.integration
def test_k3d_switch_clusters_gco2():
    """Test it choose one cluster over another with weights and then change when data changed.

    In the beginning they both have very low PV (early morning).
    Therefore Germany it choosen due to lower gco2 (243 < 350.46)

    But 08:00 pv is rising in poland and therefore renewable energy.
    """
    config = get_test_config()
    config.name = config.name + "DE_AND_PL"
    config.start.start_time_simulated = "26/02/2026 07:59:00"
    config.start.duration_time_s = 120  # enough to overlap hours
    config.workload.request_per_minute = 6
    config.weights.gco2 = 0.98
    config.weights.cost = 0.01
    config.weights.latency = 0.01
    config.clusters[0].simulated_country_code = "DE"  # DK control is simulated in Germany.
    config.clusters[1].simulated_country_code = "PL"  # PT control is simulated in Poland.
    (
        K3dTestRunner(config)
        .assert_total_requests(min_count=12, max_count=12)
        .assert_success_rate(min_rate=1)
        .assert_which_cluster_is_asserted(
            ["dk", "dk", "dk", "dk", "dk", "dk", "pt", "pt", "pt", "pt", "pt", "pt"],
            max_errors=0
        )
        .run(config.start.duration_time_s)
    )


@pytest.mark.integration
def test_k3d_switch_clusters_cost():
    """Test it choose one cluster over another with weights and then change when data changed.

    GERMANY 103.32 -> 136.05
    NETHER  105.79 -> 130.29
    So first choose Germany and afterward Netherlands
    Max errors is set to 2 as the 0.01 latency could change
    it sligtly as the prices are very similar.
    """
    config = get_test_config()
    config.name = config.name + "DE_AND_NL_COST"
    config.start.start_time_simulated = "03/03/2026 04:59:00"
    config.start.duration_time_s = 120  # enough to overlap hours
    config.workload.request_per_minute = 6
    config.weights.gco2 = 0.01
    config.weights.cost = 0.98
    config.weights.latency = 0.01
    config.clusters[0].simulated_country_code = "DE"  # DK control is simulated in Germany.
    config.clusters[1].simulated_country_code = "NL"  # PT control is simulated in Netherland.
    (
        K3dTestRunner(config)
        .assert_total_requests(min_count=12, max_count=12)
        .assert_success_rate(min_rate=1)
        .assert_which_cluster_is_asserted(
            ["dk", "dk", "dk", "dk", "dk", "dk", "pt", "pt", "pt", "pt", "pt", "pt"],
            max_errors=2
        )
        .run(config.start.duration_time_s)
    )


@pytest.mark.integration
def test_k3d_switch_clusters_latency():
    """Priotise latency therefore more or less equalised distribution."""
    config = get_test_config()
    config.name = config.name + "DE_AND_NL_COST"
    config.start.start_time_simulated = "03/03/2026 04:00:00"
    config.start.duration_time_s = 60
    config.workload.request_per_minute = 50
    config.latency.max_ms = 2000  # Expected to extend when spamming request.
    config.latency.latency_window_s = 10  # Calculate latency from the last 10 seconds request latency.
    config.weights.gco2 = 0.01
    config.weights.cost = 0.01
    config.weights.latency = 0.98
    config.clusters[0].simulated_country_code = "DE"  # DK control is simulated in Germany.
    config.clusters[1].simulated_country_code = "NL"  # PT control is simulated in Netherland.
    (
        K3dTestRunner(config)
        .assert_total_requests(min_count=100, max_count=100)
        .assert_success_rate(min_rate=0.9)
        .assert_cluster_requests("dk", 15)
        .assert_cluster_requests("pt", 15)
        .run(config.start.duration_time_s)
    )


skip_on_ci = pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="GitHub runner has no access to CROM DB"
)


@pytest.mark.integration
@skip_on_ci()
def test_k3d_switch_clusters_with_dk():
    """Test it choose one cluster over another with weights and then change when data changed.

    PV DATA:
    hour0 DK generation = 74,6
    hour0 DK consumption = 253,83
    hour0 DK gco2 = 76
    hour0 France PV = 0.0
    hour0 France gco2 = 22

    hour1 DK generation = 541,76
    hour1 DK consumption = 241,37
    hour1 DK gco2 = 64
    hour1 France PV = 0.0
    hour1 France gco2 = 21

    Therefore expected to swith from DK -> FR after one minute.
    As France gco2 is lower than DK when no surplus energy from microgrid.
    """
    config = get_test_config()

    config.name = config.name + "DK_AND_FR"
    config.start.start_time_simulated = "1/02/2025 08:59:00"
    config.start.duration_time_s = 120  # enough to overlap hours
    config.workload.request_per_minute = 6
    config.weights.gco2 = 0.98
    config.weights.cost = 0.01
    config.weights.latency = 0.01
    config.clusters[1].simulated_country_code = "FR"

    (
        K3dTestRunner(config)
        .assert_total_requests(min_count=12, max_count=12)
        .assert_success_rate(min_rate=1)
        .assert_which_cluster_is_asserted(
            ["dk", "dk", "dk", "dk", "dk", "dk", "pt", "pt", "pt", "pt", "pt", "pt"],
            max_errors=0
        )
        .run(config.start.duration_time_s)
    )
