import structlog
from datetime import datetime, timezone
from typing import TypeVar
from .models.log_models import NodeStatusLog, RequestLog, LogSent
from ..models.basemodels import WorkerNode
from ..db.postgres import (
    save_model_log,
    save_terminal_debug,
)
import os

log = structlog.get_logger()

# Change the level of logging set to DEBUG for all, info (exclude debug etc...)
LOG_LEVEL = os.getenv("LOG_LEVEL", "CRITICAL").upper()
# whether the debug, info, error, warning logs should be saved in the DB or just printed.
SAVE_LOGS_IN_DB = os.getenv("SAVE_LOGS_IN_DB", "FALSE").upper() == "TRUE"
_LOGGER_CONFIG_ID: str | None = None


def set_current_config_id(config_id: str | None):
    """Associate future log entries with a test configuration.

    All logging calls after this will tag entries with the provided config_id,
    allowing logs to be grouped and filtered by test run. Set to None to clear.
    """
    global _LOGGER_CONFIG_ID
    _LOGGER_CONFIG_ID = config_id


def _current_config_id() -> str | None:
    """Retrieve the active test configuration ID for the current logger.

    Returns None if no configuration has been set.
    """
    return _LOGGER_CONFIG_ID


def _get_terminal_logs(_, __, event_dict):
    """Intercept and store terminal logs to the database for later retrieval.

    Processes every log event, optionally saving it to the database if enabled.
    Also logs to console via structlog's ConsoleRenderer.
    """
    level = str(event_dict.get("level", "info"))
    message = str(event_dict.get("event", ""))
    config_id = _current_config_id()
    if SAVE_LOGS_IN_DB:
        save_terminal_debug(config_id, message, level, dict(event_dict))
    return event_dict


structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _get_terminal_logs,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(LOG_LEVEL),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


T = TypeVar("T")


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
    global_choose_cluster: int | None = None,
    global_total_time_ms: int | None = None,
    cluster_queue_time_ms: int | None = None,
    cluster_llama_inference_ms: int | None = None,
):
    """Record a completed inference request with timing and energy data.

    Creates a RequestLog entry capturing the full lifecycle: from dispatch to
    response, including queue time, inference time, cluster load, renewable energy
    fraction, and carbon intensity. Saves to database and logs to console.
    All values are rounded appropriately for storage.
    """
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
        global_choose_cluster=global_choose_cluster,
        global_total_time_ms=global_total_time_ms,
        cluster_queue_time_ms=cluster_queue_time_ms,
        cluster_llama_inference_ms=cluster_llama_inference_ms,
    )

    row = entry.model_dump(mode="json")

    try:
        save_model_log(_current_config_id(), entry)
    except Exception as e:
        log.warning("custom_logging.db.save_model_log_failed", error=str(e), log_type="RequestLog")
    #**row expands the dictionary into keyword fields.
    log.debug("custom_logging.request.logged", **row)


def log_sent(cluster_name: str, trace_id: str | None = None, payload: dict | None = None):
    """Record when a request is dispatched to a cluster (before response arrives).

    Marks the dispatch point in time, allowing measurement of total request
    latency by correlating with completed RequestLog entries via trace_id.
    Enables calculation of requests-per-second metrics from event timestamps.
    """
    entry = LogSent(
        timestamp=datetime.now(timezone.utc),
        cluster=cluster_name,
        trace_id=trace_id,
        payload=payload,
    )

    try:
        save_model_log(_current_config_id(), entry)
    except Exception as e:
        log.warning("custom_logging.db.save_model_log_failed", error=str(e), log_type="LogSent")

    row = entry.model_dump(mode="json")
    log.debug("custom_logging.sent.logged", **row)


def log_node_status_snapshot(cluster_name: str, node: WorkerNode):
    """Record the current state of a worker node (idle, working, or offline).

    Creates a timestamped snapshot for monitoring cluster health and reconstructing
    availability history. Enables post-run analysis of when and why nodes changed state.
    """
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
