from datetime import datetime, timezone
from ..logger import get_logs, get_terminal_debug_logs
from ..models.log_models import NodeStatusLog, RequestLog, TerminalDebugLog


def get_avg_latency_for_cluster(cluster_name: str, time_interval_s: int) -> float:
    """Return average latency (ms) for a specific cluster over the last time_interval_s seconds.

    Args:
        cluster_name: Name of the cluster to filter logs by.
        time_interval_s: How far back to look, in seconds.

    Returns:
        Average latency in milliseconds, or 0.0 if no data in the window.

    """
    now = datetime.now(timezone.utc)

    latencies = [
        entry.latency_ms
        for entry in get_logs(RequestLog)
        if entry.cluster == cluster_name
        and (now - entry.timestamp).total_seconds() <= time_interval_s
    ]

    return round(sum(latencies) / len(latencies), 2) if latencies else 0.0


def get_avg_latency(time_interval_s: int) -> float:
    """Return avg latency (ms) across requests in the last time_interval_s seconds.

    Args:
        time_interval_s: How far back to look, in seconds.

    Returns:
        Average latency in milliseconds, or 0.0 if no requests in the window.

    """
    now = datetime.now(timezone.utc)
    latencies = []

    for request_log in get_logs(RequestLog):
        age_s = (now - request_log.timestamp).total_seconds()
        if age_s <= time_interval_s:
            latencies.append(request_log.latency_ms)

    return round(sum(latencies) / len(latencies), 2) if latencies else 0.0


def get_request_logs() -> list[RequestLog]:
    """Return all request log entries as RequestLog objects."""
    return get_logs(RequestLog)


def get_worker_nodes_logs() -> list[NodeStatusLog]:
    """Return all node status snapshot entries as NodeStatusLog objects."""
    return get_logs(NodeStatusLog)


def get_terminal_debug_log_entries() -> list[TerminalDebugLog]:
    """Return terminal debug log entries as typed models."""
    return get_terminal_debug_logs()
