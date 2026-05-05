from datetime import datetime, timezone, timedelta
from ..models.log_models import NodeStatusLog, RequestLog, LogSent, MarketSnapshotLog
from ...db.postgres import read_model_logs, read_config_by_id, read_latest_node_status_log


def get_avg_latency(config_id: str, time_interval_s: int, cluster_name: str | None = None) -> float:
    """Return avg latency (ms) across requests in the last time_interval_s seconds.

    Args:
        time_interval_s: How far back to look, in seconds.

    Returns:
        Average latency in milliseconds, or 0.0 if no requests in the window.

    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=time_interval_s)
    latencies = []

    for request_log in read_model_logs(log_model_class=RequestLog, config_id=config_id, since=start):
        if not request_log.success:
            continue
        if cluster_name is not None:
            if request_log.cluster == cluster_name:
                latencies.append(request_log.latency_ms)
        else:
            latencies.append(request_log.latency_ms)

    return round(sum(latencies) / len(latencies), 2) if latencies else 0.0


def read_all_request_logs(config_id: str) -> list[RequestLog]:
    """Return all request logs by config_id."""
    if not config_id:
        return []

    try:
        return read_model_logs(log_model_class=RequestLog, config_id=config_id)
    except Exception:
        return []


def get_config_by_id(config_id: str):
    try:
        return read_config_by_id(config_id)
    except Exception:
        return None


def get_sent_logs(config_id: str, time_interval_s: int) -> list[LogSent]:
    """Return `LogSent` entries for `config_id` within the last `time_interval_s` seconds.

    This queries the DB with a time filter so callers don't need to filter by
    age themselves.
    """
    if not config_id:
        return []

    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=time_interval_s)
    try:
        return read_model_logs(log_model_class=LogSent, config_id=config_id, since=start)
    except Exception:
        return []


def read_all_sent_logs(config_id: str) -> list[LogSent]:
    """Return all sent logs by config_id."""
    if not config_id:
        return []

    try:
        return read_model_logs(log_model_class=LogSent, config_id=config_id)
    except Exception:
        return []


def get_worker_nodes_logs(
    config_id: str,
    cluster_name: str,
    node_name: str,
) -> NodeStatusLog | None:
    """Return the latest node status entry for one worker node."""
    try:
        return read_latest_node_status_log(config_id, cluster_name, node_name)
    except Exception:
        return None


def read_all_node_status_logs(config_id: str) -> list[NodeStatusLog]:
    """Read node status logs for a config as NodeStatusLog models."""
    return read_model_logs(log_model_class=NodeStatusLog, config_id=config_id)


def read_all_market_snapshot_logs(config_id: str) -> list[MarketSnapshotLog]:
    """Read market snapshot logs for a config as MarketSnapshotLog models."""
    return read_model_logs(log_model_class=MarketSnapshotLog, config_id=config_id)
