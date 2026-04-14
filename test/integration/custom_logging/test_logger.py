import csv
import json
import os
import pytest
from datetime import datetime, timedelta, timezone
from src.custom_logging.models.log_models import RequestLog
from src.custom_logging.util.log_reader import get_request_logs, get_avg_latency
from src.custom_logging.logger import (
    init_csv,
    reset_logs,
    log_request,
    log_power_decision,
    log_node_status_snapshot,
    generate_summary,
    save_summary,
    REQUEST_CSV_PATH,
    POWER_CSV_PATH,
    NODE_STATUS_CSV_PATH,
    REQUEST_CSV_FIELDS,
    POWER_CSV_FIELDS,
    NODE_STATUS_CSV_FIELDS,
)
from src.models.basemodels import ClusterConfig, WorkerNode


def _make_cluster(name: str = "denmark") -> ClusterConfig:
    """Return a minimal ClusterConfig for testing."""
    return ClusterConfig(
        name=name,
        ip="127.0.0.1",
        port="8080",
        gpio_list=[],
        simulated_country_code="DK",
        llama_service_port="11434",
    )


def _make_node(name: str = "nano1") -> WorkerNode:
    """Return a minimal WorkerNode for testing."""
    return WorkerNode(name=name, ip="127.0.0.1", status="working", gpio=1)


@pytest.fixture(autouse=True)
def clean_logs():
    """Delete log files before and after every test."""
    for path in [REQUEST_CSV_PATH, POWER_CSV_PATH, NODE_STATUS_CSV_PATH]:
        if os.path.exists(path):
            os.remove(path)

    yield

    for path in [REQUEST_CSV_PATH, POWER_CSV_PATH, NODE_STATUS_CSV_PATH]:
        if os.path.exists(path):
            os.remove(path)


def make_log_request(**overrides):
    """Call log_request with default values, optionally overriding any field."""
    cluster_name = overrides.pop("cluster", "denmark")
    node_name = overrides.pop("node", "nano1")
    defaults = dict(
        request_id="req001",
        cluster=_make_cluster(cluster_name),
        node=_make_node(node_name),
        success=True,
        latency_ms=1000.0,
        cluster_load_w=1000.0,
        renewable_fraction=0.3,
        blended_carbon_gco2_per_kwh=70.0,
        blended_cost_eur_per_kwh=0.03,
    )
    defaults.update(overrides)
    log_request(**defaults)


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
def test_init_csv_creates_node_status_csv():
    """Test that init_csv creates the node status CSV with correct headers."""
    init_csv()
    assert os.path.exists(NODE_STATUS_CSV_PATH)

    with open(NODE_STATUS_CSV_PATH, "r") as f:
        reader = csv.reader(f)
        headers = next(reader)
    assert headers == NODE_STATUS_CSV_FIELDS


@pytest.mark.integration
def test_init_csv_does_not_overwrite_existing_data():
    """Test that init_csv does not overwrite existing data."""
    init_csv()
    make_log_request()
    init_csv()

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1


# --- reset_logs ---

@pytest.mark.integration
def test_reset_logs_clears_existing_data():
    """Test that reset_logs clears existing data from all CSV files."""
    init_csv()
    make_log_request()
    reset_logs()

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 0


@pytest.mark.integration
def test_reset_logs_csvs_exist_after():
    """Test that all CSV files still exist after reset_logs."""
    reset_logs()
    assert os.path.exists(REQUEST_CSV_PATH)
    assert os.path.exists(POWER_CSV_PATH)
    assert os.path.exists(NODE_STATUS_CSV_PATH)


# --- log_request ---

@pytest.mark.integration
def test_log_request_writes_row():
    """Test that log_request writes a row to the request CSV."""
    init_csv()
    make_log_request(request_id="req001", cluster="portugal", node="nano4")

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["request_id"] == "req001"
    assert rows[0]["cluster"] == "portugal"
    assert rows[0]["node"] == "nano4"


@pytest.mark.integration
def test_log_request_rounds_latency():
    """Test that log_request rounds latency to two decimal places."""
    init_csv()
    make_log_request(latency_ms=2340.56789)

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows[0]["latency_ms"] == "2340.57"


@pytest.mark.integration
def test_log_request_writes_energy_fields():
    """Test that log_request writes the new energy fields to the CSV."""
    init_csv()
    make_log_request(
        cluster_load_w=800.0, renewable_fraction=0.5,
        blended_carbon_gco2_per_kwh=50.0, blended_cost_eur_per_kwh=0.02
    )

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows[0]["cluster_load_w"] == "800.0"
    assert rows[0]["renewable_fraction"] == "0.5"
    assert rows[0]["blended_carbon_gco2_per_kwh"] == "50.0"
    assert rows[0]["blended_cost_eur_per_kwh"] == "0.02"


@pytest.mark.integration
def test_log_request_multiple_rows_append():
    """Test that log_request appends multiple rows to the request CSV."""
    init_csv()
    for i in range(5):
        make_log_request(request_id=f"req{i}", latency_ms=1000.0 + i)

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 5


@pytest.mark.integration
def test_log_request_has_timestamp():
    """Test that log_request includes a timestamp in ISO format."""
    init_csv()
    make_log_request()

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
        action="turn_on_nodes",
        cluster="denmark",
        requested_nodes=2,
        changed_nodes=1,
        nodes=["nano2"],
        reason="scale_up_by_latency_rps",
        success=True,
        status_code=200,
        system_avg_latency_ms=2100.0,
        max_latency_ms=5000.0,
        current_rps=0.5,
        current_active_nodes=3,
        estimated_nodes_to_add=2,
    )

    with open(POWER_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["action"] == "turn_on_nodes"
    assert rows[0]["cluster"] == "denmark"
    assert rows[0]["requested_nodes"] == "2"
    assert rows[0]["changed_nodes"] == "1"
    assert rows[0]["nodes"] == "nano2"
    assert rows[0]["reason"] == "scale_up_by_latency_rps"


@pytest.mark.integration
def test_log_power_decision_writes_startup():
    """Test that log_power_decision writes a startup action to the power CSV."""
    init_csv()
    log_power_decision(
        action="turn_off_idle_nodes",
        cluster="portugal",
        requested_nodes=1,
        changed_nodes=1,
        nodes=["nano5"],
        reason="idle_timeout",
        success=False,
        status_code=502,
        system_avg_latency_ms=5800.0,
        idle_time_threshold_s=300,
        error="connection failed",
    )

    with open(POWER_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["action"] == "turn_off_idle_nodes"
    assert rows[0]["reason"] == "idle_timeout"
    assert rows[0]["success"] == "False"
    assert rows[0]["error"] == "connection failed"


# --- log_node_status_snapshot ---

@pytest.mark.integration
def test_log_node_status_snapshot_writes_one_row_per_node():
    """Test that log_node_status_snapshot writes one row per node."""
    init_csv()
    log_node_status_snapshot(_make_cluster("denmark"), [
        WorkerNode(name="worker-1", ip="127.0.0.1", status="working", gpio=1),
        WorkerNode(name="worker-2", ip="127.0.0.1", status="idle", gpio=2),
        WorkerNode(name="worker-3", ip="127.0.0.1", status="off", gpio=3),
    ])

    with open(NODE_STATUS_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 3


@pytest.mark.integration
def test_log_node_status_snapshot_counts_active_and_idle():
    """Test that log_node_status_snapshot correctly counts active and idle nodes."""
    init_csv()
    log_node_status_snapshot(_make_cluster("denmark"), [
        WorkerNode(name="worker-1", ip="127.0.0.1", status="working", gpio=1),
        WorkerNode(name="worker-2", ip="127.0.0.1", status="idle", gpio=2),
        WorkerNode(name="worker-3", ip="127.0.0.1", status="off", gpio=3),
    ])

    with open(NODE_STATUS_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert rows[0]["active_nodes"] == "1"
    assert rows[0]["idle_nodes"] == "1"


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
        make_log_request(request_id=f"req{i}")

    summary = generate_summary()
    assert summary["total_requests"] == 3


@pytest.mark.integration
def test_generate_summary_correct_avg_latency():
    """Test that generate_summary computes the correct average latency."""
    init_csv()
    make_log_request(request_id="req1", latency_ms=1000.0)
    make_log_request(request_id="req2", latency_ms=3000.0)

    summary = generate_summary()
    assert summary["avg_latency_ms"] == 2000.0


@pytest.mark.integration
def test_generate_summary_correct_cluster_distribution():
    """Test that generate_summary computes the correct cluster distribution."""
    init_csv()
    make_log_request(request_id="req1", cluster="denmark")
    make_log_request(request_id="req2", cluster="portugal")
    make_log_request(request_id="req3", cluster="portugal")

    summary = generate_summary()
    assert summary["cluster_distribution"]["denmark"] == 1
    assert summary["cluster_distribution"]["portugal"] == 2


@pytest.mark.integration
def test_generate_summary_includes_energy_fields():
    """Test that generate_summary includes gco2, cost, and renewable fields."""
    init_csv()
    make_log_request(
        cluster_load_w=1000.0,
        renewable_fraction=0.5,
        blended_carbon_gco2_per_kwh=100.0,
        blended_cost_eur_per_kwh=0.04,
        latency_ms=3600000.0,  # 1 hour in ms → 1 kWh at 1000W
    )

    summary = generate_summary()
    assert summary["total_gco2_g"] > 0
    assert summary["total_cost_eur"] > 0
    assert summary["avg_renewable_pct"] == 50.0
    assert len(summary["latency_over_time"]) == 1
    assert len(summary["cost_over_time"]) == 1


# --- save_summary ---

@pytest.mark.integration
def test_save_summary_creates_json():
    """Test that save_summary creates a JSON file with the summary data."""
    init_csv()
    make_log_request()

    summary = generate_summary()
    output_path = "logs/test_summary.json"
    save_summary(summary, output_path)

    assert os.path.exists(output_path)

    with open(output_path, "r") as f:
        loaded = json.load(f)

    assert loaded["total_requests"] == 1

    os.remove(output_path)


# --- get_request_logs ---

@pytest.mark.integration
def test_get_request_logs_returns_request_log_objects():
    """Test that get_request_logs returns a list of RequestLog objects."""
    init_csv()
    make_log_request(request_id="req001")

    result = get_request_logs()

    assert len(result) == 1
    assert isinstance(result[0], RequestLog)


@pytest.mark.integration
def test_get_request_logs_returns_all_rows():
    """Test that get_request_logs returns one entry per logged request."""
    init_csv()
    for i in range(3):
        make_log_request(request_id=f"req{i}")

    result = get_request_logs()

    assert len(result) == 3


@pytest.mark.integration
def test_get_request_logs_fields_match_logged_values():
    """Test that the returned RequestLog fields match what was logged."""
    init_csv()
    make_log_request(
        request_id="req001",
        cluster="portugal",
        node="nano4",
        latency_ms=1234.5,
        cluster_load_w=800.0,
        renewable_fraction=0.4,
        blended_carbon_gco2_per_kwh=60.0,
        blended_cost_eur_per_kwh=0.025,
    )

    result = get_request_logs()
    entry = result[0]

    assert entry.request_id == "req001"
    assert entry.cluster == "portugal"
    assert entry.node == "nano4"
    assert entry.latency_ms == 1234.5
    assert entry.cluster_load_w == 800.0
    assert entry.renewable_fraction == 0.4
    assert entry.blended_carbon_gco2_per_kwh == 60.0
    assert entry.blended_cost_eur_per_kwh == 0.025


@pytest.mark.integration
def test_get_request_logs_returns_empty_list_when_no_requests():
    """Test that get_request_logs returns an empty list when no requests have been logged."""
    init_csv()

    result = get_request_logs()

    assert result == []


# --- get_avg_latency ---

def _write_old_request(latency_ms: float, age_s: int):
    """Write a request row with a timestamp age_s seconds in the past."""
    timestamp = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    row = {
        "request_id": "old-req",
        "timestamp": timestamp.isoformat(),
        "cluster": "denmark",
        "node": "nano1",
        "success": True,
        "latency_ms": latency_ms,
        "cluster_load_w": 1000.0,
        "renewable_fraction": 0.3,
        "blended_carbon_gco2_per_kwh": 70.0,
        "blended_cost_eur_per_kwh": 0.03,
    }
    with open(REQUEST_CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUEST_CSV_FIELDS)
        writer.writerow(row)


@pytest.mark.integration
def test_get_avg_latency_returns_zero_when_no_requests():
    """Test that get_avg_latency returns 0.0 when no requests have been logged."""
    init_csv()

    result = get_avg_latency(60)

    assert result == 0.0


@pytest.mark.integration
def test_get_avg_latency_includes_recent_requests():
    """Test that get_avg_latency includes requests within the time window."""
    init_csv()
    make_log_request(latency_ms=1000.0)
    make_log_request(latency_ms=3000.0)

    result = get_avg_latency(60)

    assert result == 2000.0


@pytest.mark.integration
def test_get_avg_latency_excludes_old_requests():
    """Test that get_avg_latency excludes requests outside the time window."""
    init_csv()
    _write_old_request(latency_ms=9000.0, age_s=120)
    make_log_request(latency_ms=1000.0)

    result = get_avg_latency(60)

    assert result == 1000.0


@pytest.mark.integration
def test_get_avg_latency_returns_zero_when_all_requests_are_old():
    """Test that get_avg_latency returns 0.0 when all requests are outside the time window."""
    init_csv()
    _write_old_request(latency_ms=9000.0, age_s=120)

    result = get_avg_latency(60)

    assert result == 0.0
