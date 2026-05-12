import time
from dataclasses import dataclass
from typing import Callable, Optional

import pytest
import requests
import structlog
from sqlmodel import Session, select

from src.db.postgres import ConfigRecord, _engine
from src.models.basemodels import Config
from test.k3d.cluster_configs.test_config import get_test_config

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

    def start_test(self, config: Config) -> str:
        """Start a test by posting config to Strato API.

        Args:
            config: Test configuration to start.

        Returns:
            Config ID from the response.

        Raises:
            requests.RequestException: If API call fails.
        """
        url = f"{self.strato_api_url}/start_test"
        payload = config.model_dump()
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        config_id = result.get("config_id", config.id)
        log.info("test.started", config_id=config_id, config_name=config.name)
        return config_id

    def get_test_status(self) -> str:
        """Get current test status from Strato API.

        Returns:
            Status string: 'idle', 'running', or 'stopping'.

        Raises:
            requests.RequestException: If API call fails.
        """
        url = f"{self.strato_api_url}/test_status"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        result = response.json()
        status = result.get("status", "unknown")
        log.info("test.status_checked", status=status)
        return status

    def wait_for_test_completion(self, timeout_s: int = 120, poll_interval_s: int = 2) -> bool:
        """Wait for test to complete (status becomes 'idle').

        Args:
            timeout_s: Maximum seconds to wait before timeout.
            poll_interval_s: Seconds between status checks.

        Returns:
            True if test completed, False if timeout.
        """
        start_time = time.time()
        while time.time() - start_time < timeout_s:
            status = self.get_test_status()
            if status == "idle":
                log.info("test.completed")
                return True
            log.info("test.waiting", status=status, elapsed_s=time.time() - start_time)
            time.sleep(poll_interval_s)
        log.warning("test.timeout", timeout_s=timeout_s)
        return False

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


@dataclass
class TestScenarioDef:
    """Definition of a test scenario with config builder and assertion builder."""

    name: str
    config_builder: Callable[[], Config]
    assertion_builder: Callable[[ValidationScenario], ValidationScenario]
    description: str = ""


class TestScenarioRegistry:
    """Registry of test scenarios with builders for config and assertions.
    
    Makes it easy to add new end-to-end test scenarios that run via pytest.
    Each scenario has:
    - A config builder function (generates fresh config with unique name)
    - An assertion builder function (adds test-specific assertions)
    """

    def __init__(self):
        """Initialize empty registry."""
        self._scenarios: dict[str, TestScenarioDef] = {}

    def register(
        self,
        name: str,
        config_builder: Callable[[], Config],
        assertion_builder: Callable[[ValidationScenario], ValidationScenario],
        description: str = "",
    ) -> None:
        """Register a new test scenario.

        Args:
            name: Unique scenario name (used in test IDs).
            config_builder: Callable that returns a Config object.
            assertion_builder: Callable that takes ValidationScenario and returns it with assertions added.
            description: Human-readable scenario description.

        Example:
            def build_config():
                config = get_test_config()
                config.workload.request_per_minute = 50  # High load
                return config

            def build_assertions(scenario):
                return (
                    scenario
                    .assert_total_requests(min_count=20)
                    .assert_success_rate(min_rate=0.98)
                )

            registry.register("high_load", build_config, build_assertions, "High request load test")
        """
        self._scenarios[name] = TestScenarioDef(
            name=name,
            config_builder=config_builder,
            assertion_builder=assertion_builder,
            description=description,
        )

    def get_all(self) -> dict[str, TestScenarioDef]:
        """Get all registered scenarios."""
        return self._scenarios.copy()

    def get_names(self) -> list[str]:
        """Get all scenario names for pytest parametrization."""
        return list(self._scenarios.keys())


# Global scenario registry
TEST_SCENARIOS = TestScenarioRegistry()


# ============================================================================
# SCENARIO DEFINITIONS: Easy to add new scenarios here
# ============================================================================


def _build_default_config() -> Config:
    """Build default k3d test config with unique name."""
    return get_test_config()


def _build_default_assertions(scenario: ValidationScenario) -> ValidationScenario:
    """Add assertions for default scenario."""
    return (
        scenario
        .assert_total_requests(min_count=8)
        .assert_success_rate(min_rate=0.99)
        .assert_cluster_requests("pt", min_count=3)
        .assert_global_carbon(max_gco2=100)
    )


def _build_high_load_config() -> Config:
    """Build high-load test config."""
    config = get_test_config()
    config.workload.request_per_minute = 60  # Higher request rate
    return config


def _build_high_load_assertions(scenario: ValidationScenario) -> ValidationScenario:
    """Add assertions for high-load scenario."""
    return (
        scenario
        .assert_total_requests(min_count=20)  # More requests expected
        .assert_success_rate(min_rate=0.98)  # Slightly lower tolerance under load
        .assert_cluster_requests("dk", min_count=10)  # DK should handle more
    )


# Register scenarios (easy to add more)
TEST_SCENARIOS.register(
    "default",
    _build_default_config,
    _build_default_assertions,
    "Default k3d test: balanced load, carbon optimization"
)

TEST_SCENARIOS.register(
    "high_load",
    _build_high_load_config,
    _build_high_load_assertions,
    "High load test: 60 req/min to stress clusters"
)


# ============================================================================
# PYTEST INTEGRATION: Auto-discovered and parametrized
# ============================================================================


@pytest.mark.integration
@pytest.mark.parametrize("scenario_name", TEST_SCENARIOS.get_names())
def test_k3d_scenario(scenario_name: str) -> None:
    """Parametrized pytest test for all registered k3d scenarios.
    
    Each scenario:
    1. Generates fresh config with unique name
    2. POSTs to Strato API /start_test
    3. Polls for completion
    4. Validates scenario-specific assertions
    
    Run all scenarios:
        pytest test/integration/test_k3d_integration.py -m integration -v
    
    Run specific scenario:
        pytest test/integration/test_k3d_integration.py::test_k3d_scenario[default] -v
    """
    scenario_def = TEST_SCENARIOS.get_all()[scenario_name]
    
    # Generate fresh config
    config = scenario_def.config_builder()
    log.info("test.scenario_started", scenario=scenario_name, config_name=config.name)
    
    # Start test
    validator = ResultsValidator()
    config_id = validator.start_test(config)
    
    # Wait for completion
    completed = validator.wait_for_test_completion(timeout_s=120)
    assert completed, f"Test '{scenario_name}' did not complete within 120 seconds"
    
    # Build scenario with assertions
    validation_scenario = ValidationScenario(config.name)
    validation_scenario = scenario_def.assertion_builder(validation_scenario)
    
    # Run validation
    try:
        result = validator.run(validation_scenario)
        
        # Log results
        log.info(
            "test.scenario_passed",
            scenario=scenario_name,
            config_name=result.config_name,
            config_id=result.config_id,
            total_requests=result.total_requests,
        )
        
        # Print summary for user visibility
        print(f"\n{'='*70}")
        print(f"✓ SCENARIO PASSED: {scenario_name}")
        print(f"  Description: {scenario_def.description}")
        print(f"  Config: {result.config_name} (ID: {result.config_id})")
        print(f"  Requests: {result.total_requests} ({result.total_success} success, {result.total_failure} failure)")
        print(f"  Global Avg Carbon: {result.global_avg_carbon:.2f} gCO2/kWh")
        print(f"  Global Avg Cost: {result.global_avg_cost:.4f} EUR/kWh")
        print(f"\n  Per-Cluster Metrics:")
        for cluster_name, metrics in result.cluster_metrics.items():
            print(f"    {cluster_name}:")
            print(f"      Requests: {metrics.request_count} ({metrics.success_count} success)")
            print(f"      Avg Latency: {metrics.avg_latency_ms:.0f}ms")
            print(f"      Avg Carbon: {metrics.avg_carbon_gco2:.2f} gCO2/kWh")
            print(f"      Avg Cost: {metrics.avg_cost_eur:.4f} EUR/kWh")
        print(f"{'='*70}\n")
        
    except AssertionError as e:
        log.error("test.scenario_failed", scenario=scenario_name, error=str(e))
        print(f"\n{'='*70}")
        print(f"✗ SCENARIO FAILED: {scenario_name}")
        print(f"  Error: {e}")
        print(f"{'='*70}\n")
        raise


