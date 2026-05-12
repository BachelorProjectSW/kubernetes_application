from datetime import datetime, timezone, timedelta
from ..models.log_models import NodeStatusLog, RequestLog, LogSent, MarketSnapshotLog
from ...db.postgres import read_model_logs, read_config_by_id, read_latest_node_status_log


def get_avg_latency(config_id: str, time_interval_s: int, cluster_name: str | None = None) -> float:
    """Calculate average response time for successful requests over a time window.

    Looks back through completed requests and computes the mean latency,
    filtering by cluster if provided. Useful for monitoring overall system
    responsiveness and detecting performance degradation.

    Args:
        config_id: Configuration ID to identify which test run or scenario.
        time_interval_s: How many seconds back to analyze.
        cluster_name: Optional filter to consider only one cluster; if None, includes all.

    Returns:
        Average latency in milliseconds across successful requests, or 0.0 if none found.

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


def get_avg_llama_latency(config_id: str, time_interval_s: int, cluster_name: str | None = None) -> float:
    """Calculate average inference time (time Llama model spent running) over a time window.

    Focuses only on the model execution phase, excluding queue and overhead time.
    Useful for understanding model performance independently of infrastructure delays.
    Includes only successful requests.

    Args:
        config_id: Configuration ID to identify which test run or scenario.
        time_interval_s: How many seconds back to analyze.
        cluster_name: Optional filter to consider only one cluster; if None, includes all.

    Returns:
        Average inference time in milliseconds, or 0.0 if no requests found.

    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=time_interval_s)
    latencies = []

    for request_log in read_model_logs(log_model_class=RequestLog, config_id=config_id, since=start):
        if not request_log.success:
            continue
        if cluster_name is not None:
            if request_log.cluster == cluster_name:
                latencies.append(request_log.cluster_llama_inference_ms)
        else:
            latencies.append(request_log.cluster_llama_inference_ms)

    return round(sum(latencies) / len(latencies), 2) if latencies else 0.0


def read_all_request_logs(config_id: str) -> list[RequestLog]:
    """Retrieve all inference request records for a configuration.

    Returns the complete history of completed requests (successes and failures)
    to enable post-run analysis, debugging, and reporting.
    Returns empty list if config_id is invalid or if a database error occurs.
    """
    if not config_id:
        return []

    try:
        return read_model_logs(log_model_class=RequestLog, config_id=config_id)
    except Exception:
        return []


def get_config_by_id(config_id: str):
    """Load the test configuration object by its ID.

    Retrieves the configuration settings used for a particular test run.
    Returns None if the config is not found or if a database error occurs.
    """
    try:
        return read_config_by_id(config_id)
    except Exception:
        return None


def get_sent_logs(config_id: str, time_interval_s: int) -> list[LogSent]:
    """Retrieve records of requests dispatched to global schedueler in a recent time window.

    Each LogSent entry marks when a request left the workload scheduler and
    enter global scheduler. Used for calculate required nodes for power scheduler. 
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
    """Retrieve all request dispatch records for a configuration.

    Returns the complete history of when requests were sent to clusters,
    useful for analyzing dispatch patterns and end-to-end flow. Returns empty
    list if config_id is invalid or if a database error occurs.
    """
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
    """Retrieve the most recent status snapshot of a specific worker node.

    Useful for checking if a node is currently idle, working, or offline.
    Returns None if the node has no status record or if a database error occurs.
    """
    try:
        return read_latest_node_status_log(config_id, cluster_name, node_name)
    except Exception:
        return None


def read_all_node_status_logs(config_id: str) -> list[NodeStatusLog]:
    """Retrieve all node status records for a configuration.

    Returns a time-ordered history of worker node state changes, enabling
    reconstruction of cluster availability and performance during the test.
    """
    return read_model_logs(log_model_class=NodeStatusLog, config_id=config_id)


def read_all_market_snapshot_logs(config_id: str) -> list[MarketSnapshotLog]:
    """Retrieve hourly energy market data (carbon intensity and electricity price) for a configuration.

    Pairs each hour with its corresponding carbon and cost metrics, enabling
    post-analysis of how energy conditions affected scheduling and cost efficiency.
    """
    return read_model_logs(log_model_class=MarketSnapshotLog, config_id=config_id)
