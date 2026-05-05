from collections import Counter, defaultdict

from fastapi import HTTPException
from datetime import datetime
from ...custom_logging.models.log_models import MarketSnapshotLog, NodeStatusLog, RequestLog
from ...models.enum import WorkerStatus
from ...models.basemodels import EnergyConfig
from ...custom_logging.util.log_reader import read_all_request_logs, get_config_by_id, read_all_market_snapshot_logs, read_all_node_status_logs


def _request_energy_kwh(request: RequestLog) -> float:
    """Estimate the energy used by a single request in kWh."""
    return (request.cluster_load_w / 1000.0) * (request.latency_ms / 3_600_000.0)


def _build_node_status_timeline(node_logs: list[NodeStatusLog]) -> list[dict]:
    """Build raw node status events and aggregate active-node snapshots."""
    sorted_logs = sorted(node_logs, key=lambda entry: (entry.timestamp, entry.cluster, entry.node))
    latest_status_by_cluster: dict[str, dict[str, str]] = defaultdict(dict)
    raw_events: list[dict] = []

    for entry in sorted_logs:
        latest_status_by_cluster[entry.cluster][entry.node] = entry.status
        raw_events.append(
            {
                "timestamp": entry.timestamp.isoformat(),
                "cluster": entry.cluster,
                "node": entry.node,
                "status": entry.status,
            }
        )

    return raw_events


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
    logs: list[NodeStatusLog],
) -> float:
    """Return total energy consumed (Wh) by a cluster between start and end.

    Reconstructs power draw from NodeStatusLog entries so that state changes
    between requests are accounted for, not just snapshots at request time.
    Nodes with no history before the window are assumed to have been OFF.

    logs: if provided, use this list instead of fetching from the in-memory
    store. Pass pre-fetched database logs here when reviewing past test results.
    """
    cluster_logs = sorted(
        (e for e in logs if e.cluster == cluster_name),
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


def get_test_results(config_id: str) -> dict:
    """Return summarized test data for one config id."""
    config = get_config_by_id(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"No config found for config_id={config_id}")

    request_logs = read_all_request_logs(config_id)
    node_logs = read_all_node_status_logs(config_id)

    if not request_logs and not node_logs:
        return {
            "config_id": config_id,
            "test_name": config.name,
            "warning": "No logs found for this test run yet.",
            "request_count": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_latency_ms": 0.0,
            "total_gco2_g": 0.0,
            "total_cost_eur": 0.0,
            "gco2_over_time": [],
            "cost_over_time": [],
            "request_over_time": [],
            "service_timeout_over_time": [],
            "cluster_usage_over_time": [],
            "node_status_over_time": [],
            "cluster_distribution": {},
            "cluster_energy_wh": {},
        }

    sorted_requests = sorted(request_logs, key=lambda entry: (entry.timestamp, entry.cluster, entry.node))
    total_requests = len(sorted_requests)
    successful_requests = sum(1 for entry in sorted_requests if entry.success)
    failed_requests = total_requests - successful_requests
    successful_request_logs = [entry for entry in sorted_requests if entry.success]
    avg_latency_ms = round(
        sum(entry.latency_ms for entry in successful_request_logs)
        / successful_requests, 2
        ) if successful_requests else 0.0

    gco2_over_time: list[dict] = []
    request_over_time: list[dict] = []
    cost_over_time: list[dict] = []
    service_timeout_over_time: list[dict] = []
    cluster_usage_over_time: list[dict] = []
    cluster_distribution = Counter()
    cumulative_gco2_g = 0.0
    cumulative_cost_eur = 0.0

    for entry in sorted_requests:
        energy_kwh = _request_energy_kwh(entry)
        request_gco2_g = energy_kwh * entry.blended_carbon_gco2_per_kwh
        request_cost_eur = energy_kwh * entry.blended_cost_eur_per_kwh
        cumulative_gco2_g += request_gco2_g
        cumulative_cost_eur += request_cost_eur
        cluster_distribution[entry.cluster] += 1

        point = {
            "timestamp": entry.timestamp.isoformat(),
            "cluster": entry.cluster,
            "node": entry.node,
        }
        gco2_over_time.append(
            {
                **point,
                "gco2_g": round(request_gco2_g, 6),
                "cumulative_gco2_g": round(cumulative_gco2_g, 6),
            }
        )
        cost_over_time.append(
            {
                **point,
                "cost_eur": round(request_cost_eur, 8),
                "cumulative_cost_eur": round(cumulative_cost_eur, 8),
            }
        )
        request_over_time.append(
            {
                **point,
                "latency_ms": round(entry.latency_ms, 2),
                "ok": entry.success,
                "response_status_code": entry.response_status_code,
                "answer": entry.answer,
            }
        )
        service_timeout_over_time.append(
            {
                **point,
                "cluster_queue_time_ms": entry.cluster_queue_time_ms,
                "llama_inference_ms": entry.cluster_llama_inference_ms,
                "global_choose_cluster": entry.global_choose_cluster,
            }
        )
        cluster_usage_over_time.append(
            {
                **point,
                "ok": entry.success,
                "response_status_code": entry.response_status_code,
                "latency_ms": round(entry.latency_ms, 2),
            }
        )

    avg_renewable_pct = round(
        (sum(entry.renewable_fraction for entry in sorted_requests) / total_requests) * 100,
        1,
    ) if total_requests else 0.0

    node_status_over_time = _build_node_status_timeline(node_logs)

    started_at = min((entry.timestamp for entry in sorted_requests), default=None)
    ended_at = max((entry.timestamp for entry in sorted_requests), default=None)

    cluster_energy_wh: dict[str, float] = {}
    if started_at and ended_at:
        cluster_names = {log.cluster for log in node_logs}
        for cluster_name in cluster_names:
            cluster_energy_wh[cluster_name] = compute_cluster_energy_wh(
                cluster_name,
                started_at,
                ended_at,
                config.energy,
                logs=node_logs,
            )

    market_snapshots = read_all_market_snapshot_logs(config_id)

    snapshots_by_cluster: dict[str, list[MarketSnapshotLog]] = defaultdict(list)
    for snapshot in market_snapshots:
        snapshots_by_cluster[snapshot.cluster].append(snapshot)
    for snapshots in snapshots_by_cluster.values():
        snapshots.sort(key=lambda s: s.timestamp)

    total_gco2_g = 0.0
    total_cost_eur = 0.0

    for cluster_name, snapshots in snapshots_by_cluster.items():
        for i, snapshot in enumerate(snapshots):
            interval_start = snapshot.timestamp
            is_last_snapshot = i + 1 == len(snapshots)
            interval_end = snapshots[i + 1].timestamp if not is_last_snapshot else ended_at

            if interval_end is None or interval_start >= interval_end:
                continue

            energy_wh = compute_cluster_energy_wh(
                cluster_name, interval_start, interval_end, config.energy, logs=node_logs
            )
            energy_kwh = energy_wh / 1000.0

            total_gco2_g += energy_kwh * snapshot.carbon_gco2_per_kwh
            total_cost_eur += energy_kwh * snapshot.cost_eur_per_kwh

    return {
        "config_id": config_id,
        "test_name": config.name,
        "started_at": started_at.isoformat() if started_at else config.start.start_time_real,
        "ended_at": ended_at.isoformat() if ended_at else None,
        "request_count": total_requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "success_rate_pct": round((successful_requests / total_requests) * 100, 1) if total_requests else 0.0,
        "avg_latency_ms": avg_latency_ms,
        "total_gco2_g": round(total_gco2_g, 4),
        "total_cost_eur": round(total_cost_eur, 6),
        "avg_renewable_pct": avg_renewable_pct,
        "cluster_distribution": dict(cluster_distribution),
        "cluster_energy_wh": cluster_energy_wh,
        "gco2_over_time": gco2_over_time,
        "cost_over_time": cost_over_time,
        "request_over_time": request_over_time,
        "service_timeout_over_time": service_timeout_over_time,
        "cluster_usage_over_time": cluster_usage_over_time,
        "node_status_over_time": node_status_over_time,
    }
