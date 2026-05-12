from dataclasses import dataclass
from typing import Callable, Optional

import requests
import structlog
from sqlmodel import Session, select

from src.db.postgres import ConfigRecord, _engine
from src.models.basemodels import Config

log = structlog.get_logger()


@dataclass
class ClusterMetrics:
    """Per-cluster test execution metrics extracted from results."""

    cluster_name: str
    request_count: int
    success_count: int
    failure_count: int
    avg_latency_ms: float
    avg_carbon_gco2: float
    avg_cost_eur: float


@dataclass
class ValidationResult:
    """Aggregated test execution result across all clusters."""

    config_id: str
    config_name: str
    total_requests: int
    total_success: int
    total_failure: int
    cluster_metrics: dict[str, ClusterMetrics]
    global_avg_carbon: float
    global_avg_cost: float


class AssertionError(Exception):
    """Raised when a test assertion fails."""

    pass


class AssertionRegistry:
    """Registry of assertion functions for flexible test validation.

    Assertions are added via fluent API and executed in order.
    """

    def __init__(self):
        """Initialize empty assertion list."""
        self.assertions: list[tuple[str, Callable[[ValidationResult], None]]] = []

    def add(self, name: str, check: Callable[[ValidationResult], None]) -> "AssertionRegistry":
        """Register a new assertion check.

        Args:
            name: Human-readable assertion name for logging.
            check: Callable that raises AssertionError if test fails.

        Returns:
            Self for fluent chaining.

        """
        self.assertions.append((name, check))
        return self

    def execute_all(self, result: ValidationResult) -> None:
        """Run all registered assertions against a test result.

        Args:
            result: Aggregated test result object.

        Raises:
            AssertionError: If any assertion fails.

        """
        for name, check in self.assertions:
            try:
                check(result)
                log.info("test.assertion_passed", assertion=name)
            except AssertionError as e:
                log.error("test.assertion_failed", assertion=name, error=str(e))
                raise


class ValidationScenario:
    """Encapsulates a test scenario name with configurable assertions.

    This class provides a fluent API for registering assertions that will be
    run after test execution completes. Not a pytest test class.
    """

    def __init__(self, test_name: str, use_pattern: bool = False):
        """Initialize a scenario for a named test config.

        Args:
            test_name: Name or pattern of the test config to match in the database.
            use_pattern: If True, treat test_name as SQL LIKE pattern (e.g., 'k3d_test_%').

        """
        self.test_name = test_name
        self.use_pattern = use_pattern
        self.assertions = AssertionRegistry()

    def assert_total_requests(self, min_count: Optional[int] = None, max_count: Optional[int] = None) -> "ValidationScenario":
        """Assert on total request count across all clusters.

        Args:
            min_count: Minimum expected requests.
            max_count: Maximum expected requests.

        Returns:
            Self for fluent chaining.

        """
        def check(result: ValidationResult) -> None:
            if min_count is not None and result.total_requests < min_count:
                raise AssertionError(
                    f"Expected at least {min_count} requests, got {result.total_requests}"
                )
            if max_count is not None and result.total_requests > max_count:
                raise AssertionError(
                    f"Expected at most {max_count} requests, got {result.total_requests}"
                )

        self.assertions.add(f"total_requests({min_count}, {max_count})", check)
        return self

    def assert_success_rate(self, min_rate: float = 0.95) -> "ValidationScenario":
        """Assert on global success rate.

        Args:
            min_rate: Minimum acceptable success rate (0.0 to 1.0).

        Returns:
            Self for fluent chaining.

        """
        def check(result: ValidationResult) -> None:
            if result.total_requests == 0:
                raise AssertionError("No requests executed")
            rate = result.total_success / result.total_requests
            if rate < min_rate:
                raise AssertionError(
                    f"Success rate {rate:.2%} below minimum {min_rate:.2%}"
                )

        self.assertions.add(f"success_rate(min={min_rate})", check)
        return self

    def assert_cluster_requests(self, cluster_name: str, min_count: Optional[int] = None,
                               max_count: Optional[int] = None) -> "ValidationScenario":
        """Assert on request count for a specific cluster.

        Args:
            cluster_name: Name of the cluster to check.
            min_count: Minimum expected requests for this cluster.
            max_count: Maximum expected requests for this cluster.

        Returns:
            Self for fluent chaining.

        """
        def check(result: ValidationResult) -> None:
            if cluster_name not in result.cluster_metrics:
                raise AssertionError(f"Cluster '{cluster_name}' not found in results")
            count = result.cluster_metrics[cluster_name].request_count
            if min_count is not None and count < min_count:
                raise AssertionError(
                    f"Cluster {cluster_name}: expected at least {min_count} requests, got {count}"
                )
            if max_count is not None and count > max_count:
                raise AssertionError(
                    f"Cluster {cluster_name}: expected at most {max_count} requests, got {count}"
                )

        self.assertions.add(
            f"cluster_requests({cluster_name}, {min_count}, {max_count})",
            check
        )
        return self

    def assert_cluster_carbon(self, cluster_name: str, max_gco2: Optional[float] = None,
                             min_gco2: Optional[float] = None) -> "ValidationScenario":
        """Assert on carbon intensity for a specific cluster.

        Args:
            cluster_name: Name of the cluster.
            max_gco2: Maximum acceptable average carbon in gCO2/kWh.
            min_gco2: Minimum acceptable average carbon in gCO2/kWh.

        Returns:
            Self for fluent chaining.

        """
        def check(result: ValidationResult) -> None:
            if cluster_name not in result.cluster_metrics:
                raise AssertionError(f"Cluster '{cluster_name}' not found in results")
            carbon = result.cluster_metrics[cluster_name].avg_carbon_gco2
            if max_gco2 is not None and carbon > max_gco2:
                raise AssertionError(
                    f"Cluster {cluster_name}: carbon {carbon:.2f} exceeds max {max_gco2}"
                )
            if min_gco2 is not None and carbon < min_gco2:
                raise AssertionError(
                    f"Cluster {cluster_name}: carbon {carbon:.2f} below min {min_gco2}"
                )

        self.assertions.add(
            f"cluster_carbon({cluster_name}, max={max_gco2}, min={min_gco2})",
            check
        )
        return self

    def assert_global_carbon(self, max_gco2: float) -> "ValidationScenario":
        """Assert on global average carbon intensity.

        Args:
            max_gco2: Maximum acceptable global average carbon in gCO2/kWh.

        Returns:
            Self for fluent chaining.

        """
        def check(result: ValidationResult) -> None:
            if result.global_avg_carbon > max_gco2:
                raise AssertionError(
                    f"Global carbon {result.global_avg_carbon:.2f} exceeds max {max_gco2}"
                )

        self.assertions.add(f"global_carbon(max={max_gco2})", check)
        return self


class ResultsValidator:
    """Execute test scenario: load config, fetch results, run assertions."""

    def __init__(self, strato_api_url: str = "http://127.0.0.1:8071"):
        """Initialize test runner with API endpoint.

        Args:
            strato_api_url: Base URL of Strato API.

        """
        self.strato_api_url = strato_api_url

    def find_latest_config_by_name(self, config_name: str) -> Config | None:
        """Find the most recently created config matching a name.

        Args:
            config_name: Configuration name to search for.

        Returns:
            Config object or None if not found.

        """
        query = (
            select(ConfigRecord)
            .where(ConfigRecord.config_name == config_name)
            .order_by(ConfigRecord.created_at.desc())
        )

        with Session(_engine()) as session:
            row = session.exec(query).first()

        if row is None:
            log.warning("test.config_not_found", config_name=config_name)
            return None

        config = Config.model_validate(row.config_json)
        log.info(
            "test.config_found",
            config_name=config_name,
            config_id=config.id,
            created_at=row.created_at.isoformat()
        )
        return config

    def find_latest_config_by_pattern(self, pattern: str) -> Config | None:
        """Find the most recently created config matching a name pattern (LIKE).

        Useful for finding configs with dynamic names like 'k3d_test_%'.

        Args:
            pattern: SQL LIKE pattern to match config names.

        Returns:
            Config object or None if not found.

        """
        from sqlalchemy import func

        query = (
            select(ConfigRecord)
            .where(ConfigRecord.config_name.like(pattern))
            .order_by(ConfigRecord.created_at.desc())
        )

        with Session(_engine()) as session:
            row = session.exec(query).first()

        if row is None:
            log.warning("test.config_not_found", pattern=pattern)
            return None

        config = Config.model_validate(row.config_json)
        log.info(
            "test.config_found_by_pattern",
            pattern=pattern,
            config_name=config.name,
            config_id=config.id,
            created_at=row.created_at.isoformat()
        )
        return config

    def get_test_results(self, config_id: str) -> dict:
        """Fetch test results from Strato API.

        Args:
            config_id: Configuration ID to retrieve results for.

        Returns:
            Result payload from API.

        Raises:
            requests.RequestException: If API call fails.

        """
        url = f"{self.strato_api_url}/test_results"
        response = requests.get(url, params={"config_id": config_id}, timeout=30)
        response.raise_for_status()
        log.info("test.results_fetched", config_id=config_id)
        return response.json()

    def parse_results(self, config_name: str, api_result: dict) -> ValidationResult:
        """Parse raw API results into structured ValidationResult.

        Makes assumptions about result structure:
        - Results are organized by cluster
        - Each cluster has request logs with latency, carbon, cost fields
        - Results are aggregated to compute cluster and global metrics

        Args:
            config_name: Configuration name for logging.
            api_result: Raw API result payload.

        Returns:
            Parsed TestResult with aggregated metrics.

        """
        config_id = api_result.get("config_id", "unknown")
        cluster_metrics_dict: dict[str, ClusterMetrics] = {}

        # Parse cluster results (simplified; adjust based on actual API structure)
        request_logs = api_result.get("request_logs", [])
        carbon_logs = api_result.get("carbon_logs", [])

        # Aggregate by cluster
        cluster_data: dict[str, list[dict]] = {}
        for log_entry in request_logs:
            cluster = log_entry.get("cluster", "unknown")
            if cluster not in cluster_data:
                cluster_data[cluster] = []
            cluster_data[cluster].append(log_entry)

        # Compute per-cluster metrics
        for cluster_name, logs in cluster_data.items():
            success_count = sum(1 for log in logs if log.get("success", False))
            failure_count = len(logs) - success_count

            latencies = [log.get("latency_ms", 0) for log in logs if log.get("latency_ms")]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

            carbons = [log.get("blended_carbon_gco2_per_kwh", 0) for log in logs]
            avg_carbon = sum(carbons) / len(carbons) if carbons else 0.0

            costs = [log.get("blended_cost_eur_per_kwh", 0) for log in logs]
            avg_cost = sum(costs) / len(costs) if costs else 0.0

            cluster_metrics_dict[cluster_name] = ClusterMetrics(
                cluster_name=cluster_name,
                request_count=len(logs),
                success_count=success_count,
                failure_count=failure_count,
                avg_latency_ms=avg_latency,
                avg_carbon_gco2=avg_carbon,
                avg_cost_eur=avg_cost,
            )

        # Compute global metrics
        total_requests = sum(m.request_count for m in cluster_metrics_dict.values())
        total_success = sum(m.success_count for m in cluster_metrics_dict.values())
        total_failure = sum(m.failure_count for m in cluster_metrics_dict.values())

        global_carbons = [m.avg_carbon_gco2 for m in cluster_metrics_dict.values()]
        global_avg_carbon = sum(global_carbons) / len(global_carbons) if global_carbons else 0.0

        global_costs = [m.avg_cost_eur for m in cluster_metrics_dict.values()]
        global_avg_cost = sum(global_costs) / len(global_costs) if global_costs else 0.0

        return ValidationResult(
            config_id=config_id,
            config_name=config_name,
            total_requests=total_requests,
            total_success=total_success,
            total_failure=total_failure,
            cluster_metrics=cluster_metrics_dict,
            global_avg_carbon=global_avg_carbon,
            global_avg_cost=global_avg_cost,
        )

    def run(self, scenario: ValidationScenario) -> ValidationResult:
        """Execute a test scenario: load config, fetch results, validate assertions.

        Args:
            scenario: ValidationScenario with test name and assertions.

        Returns:
            Parsed ValidationResult.

        Raises:
            AssertionError: If any assertion fails.
            Exception: If config not found or API call fails.

        """
        # Find latest config (by pattern or exact name)
        if scenario.use_pattern:
            config = self.find_latest_config_by_pattern(scenario.test_name)
        else:
            config = self.find_latest_config_by_name(scenario.test_name)
        
        if config is None:
            raise Exception(f"Config '{scenario.test_name}' not found in database")

        # Fetch results
        api_result = self.get_test_results(config.id)

        # Parse results
        result = self.parse_results(scenario.test_name, api_result)

        # Run assertions
        scenario.assertions.execute_all(result)

        log.info(
            "test.scenario_passed",
            test_name=scenario.test_name,
            config_id=config.id,
            total_requests=result.total_requests,
        )
        return result


def validate_k3d_default_scenario():
    """Validate the default k3d scenario with typical assumptions.

    Assumptions:
    - PT cluster receives requests (carbon avoidance strategy)
    - Global carbon intensity is low (PT has good renewable output)
    - Success rate is very high (>99%)
    
    This is a manual validation function - NOT a pytest test. It should be called
    AFTER running the k3d servers and workload. Usage:
    
        python -m test.k3d.run_servers  # Start clusters and run test
        python -c "from test.integration.test_k3d_integration import validate_k3d_default_scenario; validate_k3d_default_scenario()"
    """
    scenario = (
        ValidationScenario("k3d_test_%", use_pattern=True)
        .assert_total_requests(min_count=8)  # At least 8 requests sent
        .assert_success_rate(min_rate=0.99)  # 99% success rate
        .assert_cluster_requests("pt", min_count=3)  # PT should get some requests
        .assert_global_carbon(max_gco2=100)  # Low global carbon
    )

    validator = ResultsValidator()
    result = validator.run(scenario)

    # Print result summary
    print(f"\n{'=' * 60}")
    print(f"Test: {result.config_name}")
    print(f"Config ID: {result.config_id}")
    print(f"Total Requests: {result.total_requests} ({result.total_success} success, {result.total_failure} failure)")
    print(f"Global Avg Carbon: {result.global_avg_carbon:.2f} gCO2/kWh")
    print(f"Global Avg Cost: {result.global_avg_cost:.4f} EUR/kWh")
    print("\nPer-Cluster Metrics:")
    for cluster_name, metrics in result.cluster_metrics.items():
        print(f"\n  {cluster_name}:")
        print(f"    Requests: {metrics.request_count} ({metrics.success_count} success)")
        print(f"    Avg Latency: {metrics.avg_latency_ms:.0f}ms")
        print(f"    Avg Carbon: {metrics.avg_carbon_gco2:.2f} gCO2/kWh")
        print(f"    Avg Cost: {metrics.avg_cost_eur:.4f} EUR/kWh")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    validate_k3d_default_scenario()
