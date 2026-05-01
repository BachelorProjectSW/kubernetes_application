from datetime import datetime, timezone
from ..logger import get_logs, get_terminal_debug_logs
from ..models.log_models import NodeStatusLog, RequestLog, TerminalDebugLog
from ...db.postgres import read_all_request_logs
from ...models.basemodels import EnergyConfig
from ...models.enum import WorkerStatus


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


def get_request_logs(config_id: str) -> list[RequestLog]:
    """Return request log entries for a specific config id."""
    return read_all_request_logs(config_id)


def get_worker_nodes_logs(config_id: str | None = None) -> list[NodeStatusLog]:
    """Return all node status snapshot entries as NodeStatusLog objects."""
    return get_logs(NodeStatusLog, config_id)


def get_terminal_debug_log_entries() -> list[TerminalDebugLog]:
    """Return terminal debug log entries as typed models."""
    return get_terminal_debug_logs()


def _power_for_status(status: str, energy: EnergyConfig) -> float:
    """Return instantaneous power draw in watts for a node in the given status."""
    if status == WorkerStatus.WORKING:
        return energy.node_power_active_w * energy.power_scale_factor
    if status in (WorkerStatus.IDLE, WorkerStatus.TURNING_ON, WorkerStatus.TURNING_OFF):
        return energy.node_power_idle_w * energy.power_scale_factor
    return energy.node_power_off_w * energy.power_scale_factor


def compute_cluster_energy_wh(
    cluster_name: str,
    start: datetime,
    end: datetime,
    energy: EnergyConfig,
    logs: list[NodeStatusLog] | None = None,
) -> float:
    """Return total energy consumed (Wh) by a cluster between start and end.

    Reconstructs power draw from NodeStatusLog entries so that state changes
    between requests are accounted for, not just snapshots at request time.
    Nodes with no history before the window are assumed to have been OFF.

    logs: if provided, use this list instead of fetching from the in-memory
    store. Pass pre-fetched database logs here when reviewing past test results.
    """
    all_logs = logs if logs is not None else get_logs(NodeStatusLog)

    cluster_logs = sorted(
        (e for e in all_logs if e.cluster == cluster_name),
        key=lambda e: e.timestamp,
    )

    nodes: dict[str, list[NodeStatusLog]] = {}
    for entry in cluster_logs:
        nodes.setdefault(entry.node, []).append(entry)

    total_wh = 0.0

    for entries in nodes.values():
        before = [e for e in entries if e.timestamp <= start]
        within = [e for e in entries if start < e.timestamp < end]

        if not before and not within:
            continue

        if before:
            initial_status = before[-1].status
        else:
            initial_status = WorkerStatus.OFF

        timeline: list[tuple[datetime, str | None]] = []
        timeline.append((start, initial_status))
        for e in within:
            timeline.append((e.timestamp, e.status))
        timeline.append((end, None))

        for i in range(len(timeline) - 1):
            interval_start, status = timeline[i]
            interval_end, _ = timeline[i + 1]

            duration_hours = (interval_end - interval_start).total_seconds() / 3600
            power_watts = _power_for_status(status, energy)
            total_wh += power_watts * duration_hours

    return round(total_wh, 4)
