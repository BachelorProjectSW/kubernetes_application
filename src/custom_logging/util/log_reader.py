from datetime import datetime, timezone
from ..logger import REQUEST_CSV_PATH, NODE_STATUS_CSV_PATH, get_logs
from ..models.log_models import RequestLog, NodeStatusLog


def get_avg_latency(time_interval_s: int) -> float:
    """Return avg latency (ms) across requests in the last time_interval_s seconds.

    Args:
        time_interval_s: How far back to look, in seconds.

    Returns:
        Average latency in milliseconds, or 0.0 if no requests in the window.

    """
    now = datetime.now(timezone.utc)
    latencies = []

    for request_log in get_logs(RequestLog, REQUEST_CSV_PATH):
        age_s = (now - request_log.timestamp).total_seconds()
        if age_s <= time_interval_s:
            latencies.append(request_log.latency_ms)

    return round(sum(latencies) / len(latencies), 2) if latencies else 0.0


def get_request_logs() -> list[RequestLog]:
    """Return all request log entries as RequestLog objects."""
    return get_logs(RequestLog, REQUEST_CSV_PATH)


def get_worker_nodes_logs() -> list[NodeStatusLog]:
    """Return all node status snapshot entries as NodeStatusLog objects."""
    return get_logs(NodeStatusLog, NODE_STATUS_CSV_PATH)
