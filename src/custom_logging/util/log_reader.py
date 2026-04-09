import csv
from datetime import datetime, timezone
from ....custom_logging.logger import REQUEST_CSV_PATH, NODE_STATUS_CSV_PATH
from ....custom_logging.models.log_models import RequestLog


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


def get_worker_nodes_logs() -> list[dict]:
    """Return all status snapshot rows for every node across all clusters.

    Returns:
        List of node status dicts (timestamp, cluster, node, status, active_nodes, idle_nodes).

    """
    all_rows = []
    with open(NODE_STATUS_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_rows.append(row)

    return all_rows


def get_request_logs() -> list[RequestLog]:
    """Return all request log entries as a list of RequestLog objects.

    Returns:
        List of RequestLog objects parsed from the request logs CSV.

    """
    request_logs = []
    with open(REQUEST_CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            request_logs.append(RequestLog(**row))

    return request_logs