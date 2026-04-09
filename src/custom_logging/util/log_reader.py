import csv
from datetime import datetime, timezone
from typing import TypeVar, Type
from ..logger import REQUEST_CSV_PATH, NODE_STATUS_CSV_PATH
from ..models.log_models import RequestLog, NodeStatusLog

T = TypeVar("T")


def get_logs(log_class: Type[T], path: str) -> list[T]:
    """Return logs from a CSV file parsed into the given Pydantic model class."""
    logs = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            logs.append(log_class(**row))
    return logs


def get_avg_latency(time_interval_s: int) -> float:
    """Return avg latency (ms) across requests in the last time_interval_s seconds.

    Args:
        time_interval_s: How far back to look, in seconds.

    Returns:
        Average latency in milliseconds, or 0.0 if no requests in the window.

    """
    now = datetime.now(timezone.utc)
    latencies = []

    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row["timestamp"])
            age_s = (now - ts).total_seconds()
            if age_s <= time_interval_s:
                latencies.append(float(row["latency_ms"]))

    return round(sum(latencies) / len(latencies), 2) if latencies else 0.0


def get_request_logs() -> list[RequestLog]:
    """Return all request log entries as RequestLog objects."""
    return get_logs(RequestLog, REQUEST_CSV_PATH)


def get_worker_nodes_logs() -> list[NodeStatusLog]:
    """Return all node status snapshot entries as NodeStatusLog objects."""
    return get_logs(NodeStatusLog, NODE_STATUS_CSV_PATH)
