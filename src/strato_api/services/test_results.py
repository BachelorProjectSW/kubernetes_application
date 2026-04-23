from collections import Counter, defaultdict

from fastapi import HTTPException

from ...custom_logging.models.log_models import NodeStatusLog, PowerDecisionLog, RequestLog
from ...db.postgres import read_all_node_status_logs, read_all_power_decision_logs, read_all_request_logs, read_config_by_id
from ...models.enum import WorkerStatus


def _request_energy_kwh(request: RequestLog) -> float:
    """Estimate the energy used by a single request in kWh."""
    return (request.cluster_load_w / 1000.0) * (request.latency_ms / 3_600_000.0)


def _status_counts(statuses: list[str]) -> dict[str, int]:
    """Count node status values for one cluster snapshot."""
    counts = Counter(statuses)
    return {
        "working": counts.get(WorkerStatus.WORKING.value, 0),
        "idle": counts.get(WorkerStatus.IDLE.value, 0),
        "off": counts.get(WorkerStatus.OFF.value, 0),
        "turning_on": counts.get(WorkerStatus.TURNING_ON.value, 0),
        "turning_off": counts.get(WorkerStatus.TURNING_OFF.value, 0),
    }


def _build_node_status_timeline(node_logs: list[NodeStatusLog]) -> tuple[list[dict], list[dict]]:
    """Build raw node status events and aggregate active-node snapshots."""
    sorted_logs = sorted(node_logs, key=lambda entry: (entry.timestamp, entry.cluster, entry.node))
    latest_status_by_cluster: dict[str, dict[str, str]] = defaultdict(dict)
    raw_events: list[dict] = []
    active_nodes_over_time: list[dict] = []

    for entry in sorted_logs:
        latest_status_by_cluster[entry.cluster][entry.node] = entry.status
        current_cluster_statuses = latest_status_by_cluster[entry.cluster]
        cluster_counts = _status_counts(list(current_cluster_statuses.values()))
        overall_active_nodes = sum(
            1
            for cluster_statuses in latest_status_by_cluster.values()
            for status in cluster_statuses.values()
            if status in {WorkerStatus.IDLE.value, WorkerStatus.WORKING.value}
        )

        raw_events.append(
            {
                "timestamp": entry.timestamp.isoformat(),
                "cluster": entry.cluster,
                "node": entry.node,
                "status": entry.status,
            }
        )
        active_nodes_over_time.append(
            {
                "timestamp": entry.timestamp.isoformat(),
                "cluster": entry.cluster,
                "active_nodes": cluster_counts["working"] + cluster_counts["idle"],
                "status_counts": cluster_counts,
                "overall_active_nodes": overall_active_nodes,
            }
        )

    return raw_events, active_nodes_over_time


def get_test_results(config_id: str) -> dict:
    """Return summarized test data for one config id."""
    config = read_config_by_id(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"No config found for config_id={config_id}")

    request_logs = read_all_request_logs(config_id)
    node_logs = read_all_node_status_logs(config_id)
    power_decisions = read_all_power_decision_logs(config_id)

    if not request_logs and not node_logs and not power_decisions:
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
            "latency_over_time": [],
            "cluster_usage_over_time": [],
            "active_nodes_over_time": [],
            "node_status_over_time": [],
            "power_decisions": [],
            "cluster_distribution": {},
        }

    sorted_requests = sorted(request_logs, key=lambda entry: (entry.timestamp, entry.cluster, entry.node))
    total_requests = len(sorted_requests)
    successful_requests = sum(1 for entry in sorted_requests if entry.success)
    failed_requests = total_requests - successful_requests
    avg_latency_ms = round(sum(entry.latency_ms for entry in sorted_requests) / total_requests, 2) if total_requests else 0.0

    gco2_over_time: list[dict] = []
    latency_over_time: list[dict] = []
    cost_over_time: list[dict] = []
    cluster_usage_over_time: list[dict] = []
    cluster_distribution = Counter()
    total_gco2_g = 0.0
    total_cost_eur = 0.0
    cumulative_gco2_g = 0.0
    cumulative_cost_eur = 0.0

    for entry in sorted_requests:
        energy_kwh = _request_energy_kwh(entry)
        request_gco2_g = energy_kwh * entry.blended_carbon_gco2_per_kwh
        request_cost_eur = energy_kwh * entry.blended_cost_eur_per_kwh
        cumulative_gco2_g += request_gco2_g
        cumulative_cost_eur += request_cost_eur
        total_gco2_g += request_gco2_g
        total_cost_eur += request_cost_eur
        cluster_distribution[entry.cluster] += 1

        point = {
            "timestamp": entry.timestamp.isoformat(),
            "cluster": entry.cluster,
            "node": entry.node,
            "request_id": entry.request_id,
        }
        gco2_over_time.append(
            {
                **point,
                "gco2_g": round(request_gco2_g, 6),
                "cumulative_gco2_g": round(cumulative_gco2_g, 6),
            }
        )
        latency_over_time.append(
            {
                **point,
                "latency_ms": round(entry.latency_ms, 2),
            }
        )
        cost_over_time.append(
            {
                **point,
                "cost_eur": round(request_cost_eur, 8),
                "cumulative_cost_eur": round(cumulative_cost_eur, 8),
            }
        )
        cluster_usage_over_time.append(
            {
                **point,
                "success": entry.success,
                "latency_ms": round(entry.latency_ms, 2),
                "renewable_fraction": round(entry.renewable_fraction, 4),
            }
        )

    avg_renewable_pct = round(
        (sum(entry.renewable_fraction for entry in sorted_requests) / total_requests) * 100,
        1,
    ) if total_requests else 0.0

    node_status_over_time, active_nodes_over_time = _build_node_status_timeline(node_logs)
    power_decision_payload = [
        {
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action,
            "cluster": entry.cluster,
            "node": entry.node,
            "reason": entry.reason,
            "system_avg_latency_ms": entry.system_avg_latency_ms,
        }
        for entry in sorted(power_decisions, key=lambda item: (item.timestamp, item.cluster, item.node))
    ]

    started_at = min((entry.timestamp for entry in sorted_requests), default=None)
    ended_at = max((entry.timestamp for entry in sorted_requests), default=None)

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
        "gco2_over_time": gco2_over_time,
        "latency_over_time": latency_over_time,
        "cluster_usage_over_time": cluster_usage_over_time,
        "active_nodes_over_time": active_nodes_over_time,
        "node_status_over_time": node_status_over_time,
        "power_decisions": power_decision_payload,
    }