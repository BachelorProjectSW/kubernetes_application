import threading

import structlog
import uuid
from datetime import datetime, timezone
from typing import TypeVar, Type
from .models.log_models import NodeStatusLog, PowerDecisionLog, RequestLog, TerminalDebugLog
from ..models.basemodels import ClusterConfig, WorkerNode
from ..db.postgres import (
    read_all_node_status_logs,
    read_all_power_decision_logs,
    read_all_request_logs,
    read_terminal_debug_logs,
    read_model_logs,
    save_model_log,
    save_payload_log,
    save_terminal_debug,
)

log = structlog.get_logger()

_LOGGER_CONFIG_ID: str | None = None


def set_current_config_id(config_id: str | None):
    """Set logger-scoped config id for this service instance."""
    global _LOGGER_CONFIG_ID
    _LOGGER_CONFIG_ID = config_id


def _current_config_id() -> str | None:
    return _LOGGER_CONFIG_ID


def _get_terminal_logs(_, __, event_dict):
    """Get all logs printed to terminal."""
    level = str(event_dict.get("level", "info"))
    message = str(event_dict.get("event", ""))
    config_id = _current_config_id()
    save_terminal_debug(config_id, message, level, dict(event_dict))
    return event_dict


structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _get_terminal_logs,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


T = TypeVar("T")


def get_logs(log_class: Type[T]) -> list[T]:
    """Return typed logs from DB for the requested model class."""
    try:
        config_id = _current_config_id()
        if log_class is RequestLog:
            return read_all_request_logs(config_id)  # type: ignore[return-value]
        if log_class is PowerDecisionLog:
            return read_all_power_decision_logs(config_id)  # type: ignore[return-value]
        if log_class is NodeStatusLog:
            return read_all_node_status_logs(config_id)  # type: ignore[return-value]
        return read_model_logs(log_class, _current_config_id())
    except Exception as e:
        log.warning("custom_logging.db.read_logs_failed", error=str(e), log_class=log_class.__name__)
        return []


def get_terminal_debug_logs() -> list[TerminalDebugLog]:
    """Return terminal debug log entries from DB as models."""
    try:
        return read_terminal_debug_logs(_current_config_id())
    except Exception as e:
        log.warning("custom_logging.db.read_terminal_debug_failed", error=str(e))
        return []


def log_request(
    request_id: str,
    cluster_name: str,
    worker_node_name: str,
    latency_ms: float,
    cluster_load_w: float,
    renewable_fraction: float,
    blended_carbon_gco2_per_kwh: float,
    blended_cost_eur_per_kwh: float,
    question: str | None = None,
    answer: str | None = None,
    all_content: dict | list | str | None = None,
    success: bool = True,
    trace_id: str | None = None,
    global_market_data_fetch_ms: int | None = None,
    global_cluster_scoring_ms: int | None = None,
    global_cluster_api_call_ms: int | None = None,
    global_total_time_ms: int | None = None,
):
    """Log a completed request to the CSV and console."""
    entry = RequestLog(
        request_id=request_id,
        trace_id=trace_id,
        timestamp=datetime.now(timezone.utc),
        cluster=cluster_name,
        node=worker_node_name,
        success=success,
        latency_ms=round(latency_ms, 2),
        cluster_load_w=round(cluster_load_w, 2),
        renewable_fraction=round(renewable_fraction, 4),
        blended_carbon_gco2_per_kwh=round(blended_carbon_gco2_per_kwh, 4),
        blended_cost_eur_per_kwh=round(blended_cost_eur_per_kwh, 6),
        question=question,
        answer=answer,
        all_content=all_content,
        global_market_data_fetch_ms=global_market_data_fetch_ms,
        global_cluster_scoring_ms=global_cluster_scoring_ms,
        global_cluster_api_call_ms=global_cluster_api_call_ms,
        global_total_time_ms=global_total_time_ms,
    )

    row = entry.model_dump(mode="json")

    threading.Thread(
        target=_save_model_log_bg,
        args=(_current_config_id(), entry, "RequestLog"),
        daemon=True,
    ).start()

    log.info("custom_logging.request.logged", **row)


def log_power_decision(
    action: str,
    cluster: ClusterConfig,
    node: WorkerNode,
    reason: str,
    system_avg_latency_ms: float,
):
    """Log a power scheduler decision.

    TODO: Add active_nodes_before/after, energy forecast data
    when the power scheduler is implemented.
    """
    entry = PowerDecisionLog(
        timestamp=datetime.now(timezone.utc),
        action=action,
        cluster=cluster.name,
        node=node.name,
        reason=reason,
        system_avg_latency_ms=round(system_avg_latency_ms, 2)
    )

    row = entry.model_dump(mode="json")

    try:
        save_model_log(_current_config_id(), entry)
    except Exception as e:
        log.warning("custom_logging.db.save_model_log_failed", error=str(e), log_type="PowerDecisionLog")

    log.info("custom_logging.power.decision_logged", **row)


def log_node_status_snapshot(cluster_name: str, node: WorkerNode):
    """Log a snapshot of all node statuses for a cluster."""
    timestamp = datetime.now(timezone.utc)

    entry = NodeStatusLog(
        timestamp=timestamp,
        cluster=cluster_name,
        node=node.name,
        status=node.status,
    )
    # Fire-and-forget: DB write happens in background
    threading.Thread(
        target=_save_model_log_bg,
        args=(_current_config_id(), entry, "NodeStatusLog"),
        daemon=True,
    ).start()


def generate_summary() -> dict:
    """Read request logs from DB and compute summary metrics."""
    rows = get_logs(RequestLog)

    if not rows:
        return {"error": "No requests in the database"}

    total = len(rows)
    avg_latency = sum(r.latency_ms for r in rows) / total

    # Cluster distribution
    cluster_counts: dict[str, int] = {}
    for r in rows:
        cluster_counts[r.cluster] = cluster_counts.get(r.cluster, 0) + 1

    # Energy: energy_kwh per request = cluster_load_w / 1000 * latency_ms / 3_600_000
    total_gco2_g = 0.0
    total_cost_eur = 0.0
    renewable_fractions = []
    latency_over_time = []
    cost_over_time = []

    for r in rows:
        energy_kwh = (r.cluster_load_w / 1000) * (r.latency_ms / 3_600_000)
        total_gco2_g += energy_kwh * r.blended_carbon_gco2_per_kwh
        total_cost_eur += energy_kwh * r.blended_cost_eur_per_kwh
        renewable_fractions.append(r.renewable_fraction)
        latency_over_time.append({"timestamp": r.timestamp.isoformat(), "latency_ms": r.latency_ms})
        cost_over_time.append({
            "timestamp": r.timestamp.isoformat(),
            "blended_cost_eur_per_kwh": r.blended_cost_eur_per_kwh,
        })

    avg_renewable_pct = (
        round(sum(renewable_fractions) / len(renewable_fractions) * 100, 1)
        if renewable_fractions else 0
    )

    summary = {
        "summary_id": str(uuid.uuid4()),
        "total_requests": total,
        "avg_latency_ms": round(avg_latency, 1),
        "latency_over_time": latency_over_time,
        "cluster_distribution": cluster_counts,
        "total_gco2_g": round(total_gco2_g, 4),
        "total_cost_eur": round(total_cost_eur, 6),
        "cost_over_time": cost_over_time,
        "avg_renewable_pct": avg_renewable_pct,
    }

    return summary


def save_summary(summary: dict):
    """Persist summary payload in DB instead of writing to a local file."""
    try:
        save_payload_log(_current_config_id(), "summary", summary)
    except Exception as e:
        log.warning("custom_logging.db.save_summary_failed", error=str(e))

def _save_model_log_bg(config_id, entry, log_type):
    """Background DB write — runs in a separate thread."""
    try:
        save_model_log(config_id, entry)
    except Exception as e:
        log.warning("custom_logging.db.save_model_log_failed", error=str(e), log_type=log_type)