import csv
import json
import os
import pytest
from custom_logging.logger import (
    init_csv,
    reset_logs,
    log_request,
    log_power_decision,
    generate_summary,
    save_summary,
    REQUEST_CSV_PATH,
    POWER_CSV_PATH,
    REQUEST_CSV_FIELDS,
    POWER_CSV_FIELDS,
)


@pytest.fixture(autouse=True)
def clean_logs():
    """Delete log files before and after every test."""
    for path in [REQUEST_CSV_PATH, POWER_CSV_PATH]:
        if os.path.exists(path):
            os.remove(path)

    yield

    for path in [REQUEST_CSV_PATH, POWER_CSV_PATH]:
        if os.path.exists(path):
            os.remove(path)


# --- init_csv ---

@pytest.mark.integration
def test_init_csv_creates_request_csv():
    """Test that init_csv creates the request CSV with correct headers."""
    init_csv()
    assert os.path.exists(REQUEST_CSV_PATH)

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.reader(f)
        headers = next(reader)
    assert headers == REQUEST_CSV_FIELDS


@pytest.mark.integration
def test_init_csv_creates_power_csv():
    """Test that init_csv creates the power CSV with correct headers."""
    init_csv()
    assert os.path.exists(POWER_CSV_PATH)

    with open(POWER_CSV_PATH, "r") as f:
        reader = csv.reader(f)
        headers = next(reader)
    assert headers == POWER_CSV_FIELDS


@pytest.mark.integration
def test_init_csv_does_not_overwrite_existing_data():
    """Test that init_csv does not overwrite existing data."""
    init_csv()
    log_request(
        request_id="req001",
        strategy="test",
        cluster="denmark",
        node="nano1",
        latency_ms=1000.0,
    )

    init_csv()

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1


# --- reset_logs ---

@pytest.mark.integration
def test_reset_logs_clears_existing_data():
    """Test that reset_logs clears existing data from both CSV files."""
    init_csv()
    log_request(
        request_id="req001",
        strategy="test",
        cluster="denmark",
        node="nano1",
        latency_ms=1000.0,
    )

    reset_logs()

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 0


@pytest.mark.integration
def test_reset_logs_csvs_exist_after():
    """Test that CSV files still exist after reset_logs."""
    reset_logs()
    assert os.path.exists(REQUEST_CSV_PATH)
    assert os.path.exists(POWER_CSV_PATH)


# --- log_request ---
@pytest.mark.integration
def test_log_request_writes_row():
    """Test that log_request writes a row to the request CSV."""
    init_csv()
    log_request(
        request_id="req001",
        strategy="carbon_070_cost_030",
        cluster="portugal",
        node="nano4",
        latency_ms=2340.5,
    )

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["request_id"] == "req001"
    assert rows[0]["cluster"] == "portugal"
    assert rows[0]["node"] == "nano4"
    assert rows[0]["strategy"] == "carbon_070_cost_030"


@pytest.mark.integration
def test_log_request_rounds_latency():
    """Test that log_request rounds latency to two decimal places."""
    init_csv()
    log_request(
        request_id="req001",
        strategy="test",
        cluster="denmark",
        node="nano1",
        latency_ms=2340.56789,
    )

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows[0]["latency_ms"] == "2340.57"


@pytest.mark.integration
def test_log_request_multiple_rows_append():
    """Test that log_request appends multiple rows to the request CSV."""
    init_csv()
    for i in range(5):
        log_request(
            request_id=f"req{i}",
            strategy="test",
            cluster="denmark",
            node="nano1",
            latency_ms=1000.0 + i,
        )

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 5


@pytest.mark.integration
def test_log_request_has_timestamp():
    """Test that log_request includes a timestamp in ISO format."""
    init_csv()
    log_request(
        request_id="req001",
        strategy="test",
        cluster="denmark",
        node="nano1",
        latency_ms=1000.0,
    )

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows[0]["timestamp"] != ""
    assert "T" in rows[0]["timestamp"]


# --- log_power_decision ---
@pytest.mark.integration
def test_log_power_decision_writes_shutdown():
    """Test that log_power_decision writes a shutdown action to the power CSV."""
    init_csv()
    log_power_decision(
        action="shutdown",
        cluster="denmark",
        node="nano2",
        reason="idle_poor_energy",
        system_avg_latency_ms=2100.0,
    )

    with open(POWER_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["action"] == "shutdown"
    assert rows[0]["cluster"] == "denmark"
    assert rows[0]["node"] == "nano2"
    assert rows[0]["reason"] == "idle_poor_energy"


@pytest.mark.integration
def test_log_power_decision_writes_startup():
    """Test that log_power_decision writes a startup action to the power CSV."""
    init_csv()
    log_power_decision(
        action="startup",
        cluster="portugal",
        node="nano5",
        reason="latency_high",
        system_avg_latency_ms=5800.0,
    )

    with open(POWER_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["action"] == "startup"
    assert rows[0]["reason"] == "latency_high"


# --- generate_summary ---
@pytest.mark.integration
def test_generate_summary_returns_error_when_empty():
    """Test that generate_summary returns an error when the request CSV is empty."""
    init_csv()
    summary = generate_summary()
    assert "error" in summary


@pytest.mark.integration
def test_generate_summary_correct_total():
    """Test that generate_summary computes the correct total number of requests."""
    init_csv()
    for i in range(3):
        log_request(
            request_id=f"req{i}",
            strategy="test",
            cluster="denmark",
            node="nano1",
            latency_ms=2000.0,
        )

    summary = generate_summary()
    assert summary["total_requests"] == 3


@pytest.mark.integration
def test_generate_summary_correct_avg_latency():
    """Test that generate_summary computes the correct average latency."""
    init_csv()
    log_request(
        request_id="req1",
        strategy="test",
        cluster="denmark",
        node="nano1",
        latency_ms=1000.0,
    )
    log_request(
        request_id="req2",
        strategy="test",
        cluster="denmark",
        node="nano1",
        latency_ms=3000.0,
    )

    summary = generate_summary()
    assert summary["avg_latency_ms"] == 2000.0


@pytest.mark.integration
def test_generate_summary_correct_cluster_distribution():
    """Test that generate_summary computes the correct cluster distribution."""
    init_csv()
    log_request(
        request_id="req1",
        strategy="test",
        cluster="denmark",
        node="nano1",
        latency_ms=1000.0,
    )
    log_request(
        request_id="req2",
        strategy="test",
        cluster="portugal",
        node="nano4",
        latency_ms=2000.0,
    )
    log_request(
        request_id="req3",
        strategy="test",
        cluster="portugal",
        node="nano5",
        latency_ms=2500.0,
    )

    summary = generate_summary()
    assert summary["cluster_distribution"]["denmark"] == 1
    assert summary["cluster_distribution"]["portugal"] == 2


@pytest.mark.integration
def test_generate_summary_reads_strategy_name():
    """Test that generate_summary reads the strategy name from the request CSV."""
    init_csv()
    log_request(
        request_id="req1",
        strategy="carbon_100_cost_000",
        cluster="denmark",
        node="nano1",
        latency_ms=1000.0,
    )

    summary = generate_summary()
    assert summary["strategy"] == "carbon_100_cost_000"


# --- save_summary ---
@pytest.mark.integration
def test_save_summary_creates_json():
    """Test that save_summary creates a JSON file with the summary data."""
    init_csv()
    log_request(
        request_id="req1",
        strategy="test",
        cluster="denmark",
        node="nano1",
        latency_ms=1000.0,
    )

    summary = generate_summary()
    output_path = "logs/test_summary.json"
    save_summary(summary, output_path)

    assert os.path.exists(output_path)

    with open(output_path, "r") as f:
        loaded = json.load(f)

    assert loaded["strategy"] == "test"
    assert loaded["total_requests"] == 1

    os.remove(output_path)
