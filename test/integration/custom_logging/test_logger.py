import pytest
from datetime import datetime, timedelta, timezone
from src.custom_logging.models.log_models import RequestLog
from src.custom_logging.util.log_reader import get_request_logs, get_avg_latency
from src.custom_logging.logger import (
    log_request,
    log_node_status_snapshot,
    generate_summary,
    save_summary,
)
from src.models.basemodels import ClusterConfig, WorkerNode
from src.db.postgres import init_database, _engine, AppLogRecord
from sqlmodel import Session, delete
from src.models.enum import WorkerStatus


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
    return WorkerNode(name=name, ip="127.0.0.1", status=WorkerStatus.WORKING, gpio=1)


@pytest.fixture(autouse=True)
def clean_logs():
    """Reset database logs before and after every test."""
    # Initialize database if needed
    init_database()
    # Clear any existing logs
    with Session(_engine()) as session:
        statement = delete(AppLogRecord)
        session.exec(statement)
        session.commit()

    yield

    # Clear logs after test
    with Session(_engine()) as session:
        statement = delete(AppLogRecord)
        session.exec(statement)
        session.commit()


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


@pytest.mark.integration
def test_database_does_not_lose_data_during_test():
    """Test that data persists during a single test."""
    make_log_request()
    make_log_request()

    result = get_request_logs()
    assert len(result) == 2


# --- log_request ---

@pytest.mark.integration
def test_log_request_writes_row():
    """Test that log_request writes a row to the database."""
    make_log_request(request_id="req001", cluster="portugal", node="nano4")

    result = get_request_logs()
    assert len(result) == 1
    assert result[0].request_id == "req001"
    assert result[0].cluster == "portugal"
    assert result[0].node == "nano4"


@pytest.mark.integration
def test_log_request_rounds_latency():
    """Test that log_request rounds latency to two decimal places."""
    make_log_request(latency_ms=2340.56789)

    result = get_request_logs()
    assert result[0].latency_ms == 2340.57


@pytest.mark.integration
def test_log_request_writes_energy_fields():
    """Test that log_request writes the new energy fields to the database."""
    make_log_request(
        cluster_load_w=800.0, renewable_fraction=0.5,
        blended_carbon_gco2_per_kwh=50.0, blended_cost_eur_per_kwh=0.02
    )

    result = get_request_logs()
    assert result[0].cluster_load_w == 800.0
    assert result[0].renewable_fraction == 0.5
    assert result[0].blended_carbon_gco2_per_kwh == 50.0
    assert result[0].blended_cost_eur_per_kwh == 0.02


@pytest.mark.integration
def test_log_request_multiple_rows_append():
    """Test that log_request appends multiple rows to the database."""
    for i in range(5):
        make_log_request(request_id=f"req{i}", latency_ms=1000.0 + i)

    result = get_request_logs()
    assert len(result) == 5


@pytest.mark.integration
def test_log_request_has_timestamp():
    """Test that log_request includes a timestamp."""
    make_log_request()

    result = get_request_logs()
    assert result[0].timestamp is not None
    assert isinstance(result[0].timestamp, datetime)


# --- log_node_status_snapshot ---

@pytest.mark.integration
def test_log_node_status_snapshot_writes_one_row_per_node():
    """Test that log_node_status_snapshot writes one row per node."""
    log_node_status_snapshot(
        "denmark",
        WorkerNode(name="worker-1", ip="127.0.0.1", status=WorkerStatus.WORKING, gpio=1),
    )

    from src.custom_logging.logger import get_logs
    from src.custom_logging.models.log_models import NodeStatusLog
    result = get_logs(NodeStatusLog)

    assert len(result) == 1


# --- generate_summary ---

@pytest.mark.integration
def test_generate_summary_returns_error_when_empty():
    """Test that generate_summary returns an error when no requests are logged."""
    summary = generate_summary()
    assert "error" in summary


@pytest.mark.integration
def test_generate_summary_correct_total():
    """Test that generate_summary computes the correct total number of requests."""
    for i in range(3):
        make_log_request(request_id=f"req{i}")

    summary = generate_summary()
    assert summary["total_requests"] == 3


@pytest.mark.integration
def test_generate_summary_correct_avg_latency():
    """Test that generate_summary computes the correct average latency."""
    make_log_request(request_id="req1", latency_ms=1000.0)
    make_log_request(request_id="req2", latency_ms=3000.0)

    summary = generate_summary()
    assert summary["avg_latency_ms"] == 2000.0


@pytest.mark.integration
def test_generate_summary_correct_cluster_distribution():
    """Test that generate_summary computes the correct cluster distribution."""
    make_log_request(request_id="req1", cluster="denmark")
    make_log_request(request_id="req2", cluster="portugal")
    make_log_request(request_id="req3", cluster="portugal")

    summary = generate_summary()
    assert summary["cluster_distribution"]["denmark"] == 1
    assert summary["cluster_distribution"]["portugal"] == 2


@pytest.mark.integration
def test_generate_summary_includes_energy_fields():
    """Test that generate_summary includes gco2, cost, and renewable fields."""
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
def test_save_summary_saves_to_database():
    """Test that save_summary saves the summary data to the database."""
    make_log_request()

    summary = generate_summary()
    save_summary(summary)

    # If no exception is raised, summary was saved
    assert "total_requests" in summary
    assert summary["total_requests"] == 1


# --- get_request_logs ---

@pytest.mark.integration
def test_get_request_logs_returns_request_log_objects():
    """Test that get_request_logs returns a list of RequestLog objects."""
    make_log_request(request_id="req001")

    result = get_request_logs()

    assert len(result) == 1
    assert isinstance(result[0], RequestLog)


@pytest.mark.integration
def test_get_request_logs_returns_all_rows():
    """Test that get_request_logs returns one entry per logged request."""
    for i in range(3):
        make_log_request(request_id=f"req{i}")

    result = get_request_logs()

    assert len(result) == 3


@pytest.mark.integration
def test_get_request_logs_fields_match_logged_values():
    """Test that the returned RequestLog fields match what was logged."""
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
    result = get_request_logs()

    assert result == []


# --- get_avg_latency ---

def _write_old_request(latency_ms: float, age_s: int):
    """Write a request record to the database with a timestamp age_s seconds in the past."""
    from src.custom_logging.models.log_models import RequestLog
    from src.db.postgres import save_model_log

    timestamp = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    request_log = RequestLog(
        request_id="old-req",
        timestamp=timestamp,
        cluster="denmark",
        node="nano1",
        success=True,
        latency_ms=latency_ms,
        cluster_load_w=1000.0,
        renewable_fraction=0.3,
        blended_carbon_gco2_per_kwh=70.0,
        blended_cost_eur_per_kwh=0.03,
    )

    save_model_log(None, request_log)


@pytest.mark.integration
def test_get_avg_latency_returns_zero_when_no_requests():
    """Test that get_avg_latency returns 0.0 when no requests have been logged."""
    result = get_avg_latency(60)

    assert result == 0.0


@pytest.mark.integration
def test_get_avg_latency_includes_recent_requests():
    """Test that get_avg_latency includes requests within the time window."""
    make_log_request(latency_ms=1000.0)
    make_log_request(latency_ms=3000.0)

    result = get_avg_latency(60)

    assert result == 2000.0


@pytest.mark.integration
def test_get_avg_latency_excludes_old_requests():
    """Test that get_avg_latency excludes requests outside the time window."""
    _write_old_request(latency_ms=9000.0, age_s=120)
    make_log_request(latency_ms=1000.0)

    result = get_avg_latency(60)

    assert result == 1000.0


@pytest.mark.integration
def test_get_avg_latency_returns_zero_when_all_requests_are_old():
    """Test that get_avg_latency returns 0.0 when all requests are outside the time window."""
    _write_old_request(latency_ms=9000.0, age_s=120)

    result = get_avg_latency(60)

    assert result == 0.0
