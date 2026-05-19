from datetime import datetime, timedelta, timezone

import pytest

from src.global_api.util.time_utils import SIMULATED_TIME_FORMAT, compute_simulated_now
from test.k3d.cluster_configs.test_config import get_test_config


pytestmark = pytest.mark.unit


def _simulated_start() -> datetime:
    """Parse the simulated start string from the canonical test config."""
    raw = get_test_config().start.start_time_simulated
    return datetime.strptime(raw, SIMULATED_TIME_FORMAT).replace(tzinfo=timezone.utc)


def test_zero_elapsed_returns_simulated_start():
    """When real start is 'now', simulated time equals the simulated start."""
    config = get_test_config()
    real_start = datetime.now(timezone.utc).isoformat()

    result = compute_simulated_now(config.start.start_time_simulated, real_start)

    assert abs((result - _simulated_start()).total_seconds()) < 2


def test_elapsed_real_time_advances_the_simulated_clock():
    """An hour of real elapsed time advances simulated time by an hour."""
    config = get_test_config()
    real_start = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    result = compute_simulated_now(config.start.start_time_simulated, real_start)

    expected = _simulated_start() + timedelta(hours=1)
    assert abs((result - expected).total_seconds()) < 2


def test_accepts_zulu_suffix_real_start():
    """A real-start timestamp using a trailing 'Z' is parsed as UTC."""
    config = get_test_config()
    real_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    result = compute_simulated_now(config.start.start_time_simulated, real_start)

    assert result.tzinfo is not None
    assert abs((result - _simulated_start()).total_seconds()) < 5


def test_naive_real_start_is_treated_as_utc():
    """A real-start timestamp without tz info is assumed to be UTC."""
    config = get_test_config()
    real_start = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    result = compute_simulated_now(config.start.start_time_simulated, real_start)

    assert abs((result - _simulated_start()).total_seconds()) < 5


def test_invalid_simulated_format_raises_value_error():
    """A malformed simulated start string fails fast with ValueError."""
    with pytest.raises(ValueError):
        compute_simulated_now("not-a-date", datetime.now(timezone.utc).isoformat())
