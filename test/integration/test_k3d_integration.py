"""Simple K3d integration tests driven directly from the raw /test_results payload.

How to add a new scenario:
    1. Copy one of the tests below
    2. Start with get_test_config()
    3. Modify the config you care about
    4. Chain assertions on K3dTestRunner
    5. Call .run()

Example:
    # @pytest.mark.integration
    # def test_k3d_my_scenario():
    #     config = get_test_config()
    #     config.workload.request_per_minute = 30
    #     K3dTestRunner(config) \
    #         .assert_total_requests(min_count=10) \
    #         .assert_success_rate(min_rate=0.98) \
    #         .run()
"""

from __future__ import annotations

import time
from typing import Callable

import pytest
import requests

from src.models.basemodels import Config
from test.k3d.cluster_configs.test_config import get_test_config


class K3dTestRunner:
    """Start a test, wait for completion, fetch the raw summary, and run assertions."""

    def __init__(self, config: Config, api_url: str = "http://127.0.0.1:8071"):
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

    def assert_cluster_requests(self, cluster_name: str, min_count: int | None = None, max_count: int | None = None):
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

    def assert_global_carbon(self, max_gco2: float):
        """Assert the global carbon total from the raw summary."""

        def check(summary: dict) -> None:
            value = float(summary.get("total_gco2_g", 0.0))
            if value > max_gco2:
                raise AssertionError(f"Global carbon {value:.2f} > {max_gco2}")

        self.assertions.append((f"global_carbon(max={max_gco2})", check))
        return self

    def _start_test(self) -> str:
        print(f"[START] POST {self.api_url}/start_test")
        response = requests.post(
            f"{self.api_url}/start_test",
            json=self.config.model_dump(),
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        config_id = payload.get("config_id") or self.config.id
        if config_id is None:
            raise RuntimeError("start_test did not return a config_id")
        print(f"[START] config_id={config_id}")
        return config_id

    def _wait_for_completion(self, timeout_s: int = 120, poll_interval_s: int = 2) -> None:
        print(f"[WAIT] waiting up to {timeout_s}s")
        started_at = time.time()
        while time.time() - started_at < timeout_s:
            response = requests.get(f"{self.api_url}/test_status", timeout=30)
            response.raise_for_status()
            status = response.json().get("status", "unknown")
            if status == "idle":
                print(f"[DONE] completed in {time.time() - started_at:.1f}s")
                return
            print(f"[WAIT] status={status}")
            time.sleep(poll_interval_s)
        raise TimeoutError(f"Test did not complete within {timeout_s} seconds")

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

    def run(self) -> dict:
        config_id = self._start_test()
        self._wait_for_completion()
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
        .assert_total_requests(min_count=8)
        .assert_success_rate(min_rate=0.99)
        .assert_cluster_requests("pt", min_count=3)
        .assert_global_carbon(max_gco2=100)
        .run()
    )


@pytest.mark.integration
def test_k3d_high_load():
    """Higher request-rate scenario."""
    config = get_test_config()
    config.workload.request_per_minute = 60

    (
        K3dTestRunner(config)
        .assert_total_requests(min_count=20)
        .assert_success_rate(min_rate=0.98)
        .assert_cluster_requests("dk", min_count=10)
        .run()
    )


# To add test_k3d_my_scenario, copy one of the tests above,
# import get_test_config(), change the fields you need, and chain
# the assertions that matter for that scenario.
