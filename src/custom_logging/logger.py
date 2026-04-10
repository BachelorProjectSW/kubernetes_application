import structlog
import csv
import json
import os
import uuid
from datetime import datetime, timezone
from typing import TypeVar, Type

from .models.log_models import RequestLog, PowerDecisionLog, NodeStatusLog
from ..models.basemodels import ClusterConfig, WorkerNode
from ..models.enum import WorkerStatus

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()

REQUEST_CSV_FIELDS = list(RequestLog.model_fields.keys())
REQUEST_CSV_PATH = "logs/requests.csv"

POWER_CSV_FIELDS = list(PowerDecisionLog.model_fields.keys())
POWER_CSV_PATH = "logs/power_decisions.csv"

NODE_STATUS_CSV_FIELDS = list(NodeStatusLog.model_fields.keys())
NODE_STATUS_CSV_PATH = "logs/node_status.csv"


def init_csv():
    """Create all CSV files with headers if they don't exist."""
    os.makedirs("logs", exist_ok=True)

    for path, fields in [
        (REQUEST_CSV_PATH, REQUEST_CSV_FIELDS),
        (POWER_CSV_PATH, POWER_CSV_FIELDS),
        (NODE_STATUS_CSV_PATH, NODE_STATUS_CSV_FIELDS),
    ]:
        if not os.path.exists(path):
            with open(path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
            log.info("csv.created", path=path)


T = TypeVar("T")


def get_logs(log_class: Type[T], path: str) -> list[T]:
    """Return logs from a CSV file parsed into the given Pydantic model class."""
    logs = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            logs.append(log_class(**row))
    return logs


def reset_logs():
    """Delete existing logs and create fresh CSVs. Call at the start of experiment run."""
    for path in [REQUEST_CSV_PATH, POWER_CSV_PATH, NODE_STATUS_CSV_PATH]:
        if os.path.exists(path):
            os.remove(path)
    init_csv()
    log.info("logs.reset")


def log_request(
    request_id: str,
    cluster: ClusterConfig,
    node: WorkerNode,
    latency_ms: float,
    cluster_load_w: float,
    renewable_fraction: float,
    blended_carbon_gco2_per_kwh: float,
    blended_cost_eur_per_kwh: float,
    success: bool,
):
    """Log a completed request to the CSV and console."""
    entry = RequestLog(
        request_id=request_id,
        timestamp=datetime.now(timezone.utc),
        cluster=cluster.name,
        node=node.name,
        success=success,
        latency_ms=round(latency_ms, 2),
        cluster_load_w=round(cluster_load_w, 2),
        renewable_fraction=round(renewable_fraction, 4),
        blended_carbon_gco2_per_kwh=round(blended_carbon_gco2_per_kwh, 4),
        blended_cost_eur_per_kwh=round(blended_cost_eur_per_kwh, 6),
    )

    row = entry.model_dump(mode="json")

    with open(REQUEST_CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUEST_CSV_FIELDS)
        writer.writerow(row)

    log.info("request.logged", **row)


def log_power_decision(
    action: str,
    cluster: ClusterConfig,
    node: WorkerNode,
    reason: str,
    system_avg_latency_ms: float,
):
    """Log a power scheduler decision to the CSV and console.

    TODO: Add active_nodes_before/after, energy forecast data
    when the power scheduler is implemented.
    """
    entry = PowerDecisionLog(
        timestamp=datetime.now(timezone.utc),
        action=action,
        cluster=cluster.name,
        node=node.name,
        reason=reason,
        system_avg_latency_ms=round(system_avg_latency_ms, 2)
    )

    row = entry.model_dump(mode="json")

    with open(POWER_CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=POWER_CSV_FIELDS)
        writer.writerow(row)

    log.info(f"power.{action}", **row)


def log_node_status_snapshot(cluster: ClusterConfig, node_statuses: list[WorkerNode]):
    """Log a snapshot of all node statuses for a cluster."""
    timestamp = datetime.now(timezone.utc)
    active_nodes = sum(1 for n in node_statuses if n.status == WorkerStatus.WORKING)
    idle_nodes = sum(1 for n in node_statuses if n.status == WorkerStatus.IDLE)

    with open(NODE_STATUS_CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=NODE_STATUS_CSV_FIELDS)
        for node in node_statuses:
            entry = NodeStatusLog(
                timestamp=timestamp,
                cluster=cluster.name,
                node=node.name,
                status=node.status,
                active_nodes=active_nodes,
                idle_nodes=idle_nodes,
            )
            writer.writerow(entry.model_dump(mode="json"))

    log.info("node_status.snapshot", cluster=cluster.name, active=active_nodes, idle=idle_nodes)


def generate_summary(csv_path: str = REQUEST_CSV_PATH) -> dict:
    """Read the request CSV and compute summary metrics."""
    rows = get_logs(RequestLog, csv_path)

    if not rows:
        return {"error": "No requests in the CSV"}

    total = len(rows)
    avg_latency = sum(r.latency_ms for r in rows) / total

    # Cluster distribution
    cluster_counts: dict[str, int] = {}
    for r in rows:
        cluster_counts[r.cluster] = cluster_counts.get(r.cluster, 0) + 1

    # Energy: energy_kwh per request = cluster_load_w / 1000 * latency_ms / 3_600_000
    total_gco2_g = 0.0
    total_cost_eur = 0.0
    renewable_fractions = []
    latency_over_time = []
    cost_over_time = []

    for r in rows:
        energy_kwh = (r.cluster_load_w / 1000) * (r.latency_ms / 3_600_000)
        total_gco2_g += energy_kwh * r.blended_carbon_gco2_per_kwh
        total_cost_eur += energy_kwh * r.blended_cost_eur_per_kwh
        renewable_fractions.append(r.renewable_fraction)
        latency_over_time.append({"timestamp": r.timestamp.isoformat(), "latency_ms": r.latency_ms})
        cost_over_time.append({
            "timestamp": r.timestamp.isoformat(),
            "blended_cost_eur_per_kwh": r.blended_cost_eur_per_kwh,
        })

    avg_renewable_pct = (
        round(sum(renewable_fractions) / len(renewable_fractions) * 100, 1)
        if renewable_fractions else 0
    )

    summary = {
        "summary_id": str(uuid.uuid4()),
        "total_requests": total,
        "avg_latency_ms": round(avg_latency, 1),
        "latency_over_time": latency_over_time,
        "cluster_distribution": cluster_counts,
        "total_gco2_g": round(total_gco2_g, 4),
        "total_cost_eur": round(total_cost_eur, 6),
        "cost_over_time": cost_over_time,
        "avg_renewable_pct": avg_renewable_pct,
    }

    return summary


# TODO - save to database instead of local JSON file when database is implemented
def save_summary(summary: dict, output_path: str = "logs/summary.json"):
    """Save the summary dictionary to a JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)
