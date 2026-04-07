import random
import pytest
from collections import Counter
from src.strato_api.services.workload.generator import generate_workload


@pytest.mark.unit
def test_returns_empty_on_invalid_input():
    """Test errorhandling."""
    assert generate_workload(0, 10) == []
    assert generate_workload(10, 0) == []
    assert generate_workload(-1, 10) == []
    assert generate_workload(10, -5) == []


@pytest.mark.unit
def test_steady_pattern_spacing():
    """Test that each request is within 2 seconds (due to small random timestamp)."""
    timestamps = generate_workload(60, 60, pattern="steady", seed=42)

    # Differences between timestamps should be roughly ~1 second
    for i in range(len(timestamps) - 1):
        avg_diff = timestamps[i + 1] - timestamps[i]
        assert avg_diff <= 2


@pytest.mark.unit
def test_peaks_pattern_basic_distribution():
    """Test peaks have very low, (some seconds with 0 request, some with over 10)."""
    timestamps = generate_workload(
        duration_s=10000,
        rpm=200,
        pattern="peaks",
        seed=random.uniform(0, 10000),
        peakiness=2.0,
    )

    buckets = Counter(int(t) for t in timestamps)

    min_per_sec = min(buckets.values())
    max_per_sec = max(buckets.values())

    assert min_per_sec <= 2
    assert max_per_sec >= 10
    assert max_per_sec > (min_per_sec + 10)  # Ensure its at least 10 request bigger than min.


@pytest.mark.unit
def test_deterministic_with_same_seed():
    """Test deterministic."""
    t1 = generate_workload(60, 10, seed=123)
    t2 = generate_workload(60, 10, seed=123)

    assert t1 == t2


@pytest.mark.unit
def test_different_seed_produces_different_output():
    """Test diffent seeds."""
    t1 = generate_workload(60, 10, seed=123)
    t2 = generate_workload(60, 10, seed=456)

    assert t1 != t2
