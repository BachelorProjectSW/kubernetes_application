import pytest

from src.global_api.services.validate_config import validate_config_values
from test.k3d.cluster_configs.test_config import get_test_config


pytestmark = pytest.mark.unit


def test_validate_config_values_accepts_valid_test_config():
    """The default k3d test config should pass value-level validation."""
    config = get_test_config()

    assert validate_config_values(config) == []


def test_validate_config_values_reports_common_errors():
    """Multiple invalid fields should be reported in a single validation pass."""
    config = get_test_config()
    config.start.duration_time_s = 0
    config.workload.request_per_minute = 0
    config.weights.gco2 = 0.9
    config.weights.cost = 0.9
    config.weights.latency = 0.9
    config.clusters[1].name = config.clusters[0].name
    config.clusters[0].gpio_list = []
    config.question.question = "   "
    config.question.max_output_tokens = 0
    config.latency.max_ms = 0
    config.latency.latency_window_s = 0
    config.start.start_time_simulated = "not-a-date"

    errors = validate_config_values(config)

    assert "duration must be > 0" in errors
    assert "request per minute must be > 0" in errors
    assert any(error.startswith("weights must sum to 1.0") for error in errors)
    assert "duplicate cluster names found" in errors
    assert "cluster dk has no GPIOs configured" in errors
    assert "question cannot be empty" in errors
    assert "max_output_tokens must be > 0" in errors
    assert "latency must be > 0" in errors
    assert "start time invalid format, expected DD/MM/YYYY HH:MM:SS" in errors
