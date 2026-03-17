import structlog
import csv
import json
import os
from datetime import datetime, timezone

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

REQUEST_CSV_FIELDS = [
    "request_id",
    "timestamp",
    "strategy",
    "cluster",
    "node",
    "latency_ms",
    "carbon_intensity_gco2_kwh",
    "electricity_price",
    "renewable_output_w",
    "cluster_load_w",
]

REQUEST_CSV_PATH = "logs/requests.csv"

POWER_CSV_FIELDS = [
    "timestamp",
    "action",
    "cluster",
    "node",
    "reason",
    "system_avg_latency_ms",
    "active_nodes_before",
    "active_nodes_after",
]

POWER_CSV_PATH = "logs/power_decisions.csv"


def init_csv():
    """Create both CSV files with headers if they don't exist."""
    os.makedirs("logs", exist_ok=True)

    if not os.path.exists(REQUEST_CSV_PATH):
        with open(REQUEST_CSV_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=REQUEST_CSV_FIELDS)
            writer.writeheader()
        log.info("csv.created", path=REQUEST_CSV_PATH)

    if not os.path.exists(POWER_CSV_PATH):
        with open(POWER_CSV_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=POWER_CSV_FIELDS)
            writer.writeheader()
        log.info("csv.created", path=POWER_CSV_PATH)


def reset_logs():
    """Delete existing logs and create fresh CSVs. Call at the start of experiment run."""
    for path in [REQUEST_CSV_PATH, POWER_CSV_PATH]:
        if os.path.exists(path):
            os.remove(path)
    init_csv()
    log.info("logs.reset")


def log_request(
    request_id: str,
    strategy: str,
    cluster: str,
    node: str,
    latency_ms: float,
):
    """Log a completed request to the CSV and console."""
    row = {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "cluster": cluster,
        "node": node,
        "latency_ms": round(latency_ms, 2),
    }

    with open(REQUEST_CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUEST_CSV_FIELDS)
        writer.writerow(row)

    log.info("request.logged", **row)


def log_power_decision(
    action: str,
    cluster: str,
    node: str,
    reason: str,
    system_avg_latency_ms: float,
):
    """Log a power scheduler decision to the CSV and console.

    TODO: Add active_nodes_before/after, energy forecast data
    when the power scheduler is implemented.
    """
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "cluster": cluster,
        "node": node,
        "reason": reason,
        "system_avg_latency_ms": round(system_avg_latency_ms, 2),
    }

    with open(POWER_CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=POWER_CSV_FIELDS)
        writer.writerow(row)

    log.info(f"power.{action}", **row)


def generate_summary(csv_path: str = REQUEST_CSV_PATH) -> dict:
    """Read the request CSV and compute summary metrics."""
    rows = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return {"error": "No requests in the CSV"}

    total = len(rows)

    # Average latency
    latencies = []
    for r in rows:
        if r.get("latency_ms"):
            latencies.append(float(r["latency_ms"]))
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    # Cluster distribution
    cluster_counts = {}
    for r in rows:
        cluster = r.get("cluster", "unknown")
        if cluster in cluster_counts:
            cluster_counts[cluster] = cluster_counts[cluster] + 1
        else:
            cluster_counts[cluster] = 1

    # Strategy name
    strategy = rows[0].get("strategy", "unknown")

    summary = {
        "strategy": strategy,
        "total_requests": total,
        "avg_latency_ms": round(avg_latency, 1),
        "cluster_distribution": cluster_counts,
    }

    return summary


def save_summary(summary: dict, output_path: str = "logs/summary.json"):
    """Save the summary dictionary to a JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)
