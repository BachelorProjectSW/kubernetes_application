import structlog
import uuid
from datetime import datetime, timezone
from typing import TypeVar, Type
from .models.log_models import NodeStatusLog, RequestLog, TerminalDebugLog
from ..models.basemodels import WorkerNode
from ..db.postgres import (
    read_all_node_status_logs,
    read_all_request_logs,
    read_terminal_debug_logs,
    read_model_logs,
    save_model_log,
    save_terminal_debug,
)
import os

log = structlog.get_logger()

LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()


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
        # _get_terminal_logs,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(LOG_LEVEL),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


T = TypeVar("T")


def get_logs(log_class: Type[T], config_id: str | None = None) -> list[T]:
    """Return typed logs from DB for the requested model class."""
    try:
        effective_config_id = _current_config_id() if config_id is None else config_id
        if log_class is RequestLog:
            return read_all_request_logs(effective_config_id)  # type: ignore[return-value]
        if log_class is NodeStatusLog:
            return read_all_node_status_logs(effective_config_id)  # type: ignore[return-value]
        return read_model_logs(log_class, effective_config_id)
    except Exception as e:
        log.warning(
            "custom_logging.db.read_logs_failed",
            error=str(e),
            log_class=log_class.__name__,
            config_id=config_id,
        )
        return []


def get_terminal_debug_logs() -> list[TerminalDebugLog]:
    """Return terminal debug log entries from DB as models."""
    try:
        return read_terminal_debug_logs(_current_config_id())
    except Exception as e:
        log.warning("custom_logging.db.read_terminal_debug_failed", error=str(e))
        return []


def log_request(
    cluster_name: str,
    worker_node_name: str,
    latency_ms: float,
    cluster_load_w: float,
    renewable_fraction: float,
    blended_carbon_gco2_per_kwh: float,
    blended_cost_eur_per_kwh: float,
    question: str | None = None,
    answer: str | None = None,
    response_status_code: int | None = None,
    all_content: dict | list | str | None = None,
    success: bool = True,
    trace_id: str | None = None,
    global_market_data_fetch_ms: int | None = None,
    global_cluster_scoring_ms: int | None = None,
    global_cluster_api_call_ms: int | None = None,
    global_total_time_ms: int | None = None,
    cluster_queue_time_ms: int | None = None,
    cluster_llama_inference_ms: int | None = None,
):
    """Log a completed request to the CSV and console."""
    entry = RequestLog(
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
        response_status_code=response_status_code,
        all_content=all_content,
        global_market_data_fetch_ms=global_market_data_fetch_ms,
        global_cluster_scoring_ms=global_cluster_scoring_ms,
        global_cluster_api_call_ms=global_cluster_api_call_ms,
        global_total_time_ms=global_total_time_ms,
        cluster_queue_time_ms=cluster_queue_time_ms,
        cluster_llama_inference_ms=cluster_llama_inference_ms,
    )

    row = entry.model_dump(mode="json")

    try:
        save_model_log(_current_config_id(), entry)
    except Exception as e:
        log.warning("custom_logging.db.save_model_log_failed", error=str(e), log_type="RequestLog")

    log.info("custom_logging.request.logged", **row)


def log_node_status_snapshot(cluster_name: str, node: WorkerNode):
    """Log a snapshot of all node statuses for a cluster."""
    timestamp = datetime.now(timezone.utc)

    entry = NodeStatusLog(
        timestamp=timestamp,
        cluster=cluster_name,
        node=node.name,
        status=node.status
    )
    try:
        save_model_log(_current_config_id(), entry)
    except Exception as e:
        log.warning("custom_logging.db.save_model_log_failed", error=str(e), log_type="NodeStatusLog")

