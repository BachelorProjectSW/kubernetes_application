from pydantic import BaseModel
from datetime import datetime
from typing import Any


class RequestLog(BaseModel):
    """Model for a single completed request log entry."""

    trace_id: str | None = None
    timestamp: datetime
    cluster: str
    node: str
    success: bool
    latency_ms: float
    cluster_load_w: float
    renewable_fraction: float
    blended_carbon_gco2_per_kwh: float
    blended_cost_eur_per_kwh: float
    question: str | None = None
    answer: str | None = None
    response_status_code: int | None = None
    all_content: Any | None = None
    global_choose_cluster: int | None = None
    global_total_time_ms: int | None = None
    cluster_queue_time_ms: int | None = None
    cluster_llama_inference_ms: int | None = None


class NodeStatusLog(BaseModel):
    """Status of a single node's status at a given timestamp."""

    timestamp: datetime
    cluster: str
    node: str
    status: str


class MarketSnapshotLog(BaseModel):
    """Carbon intensity and electricity price for one cluster at one simulated hour.

    Written once per (config_id, cluster, simulated_hour) to give test_results
    an accurate hourly rate to pair with the continuous energy reconstruction.
    """

    timestamp: datetime
    simulated_hour: datetime
    cluster: str
    carbon_gco2_per_kwh: float
    cost_eur_per_kwh: float


class TerminalDebugLog(BaseModel):
    """Model for terminal debug entries stored in the database."""

    config_id: str | None
    message: str
    payload: dict | None = None
    created_at: datetime


class LogSent(BaseModel):
    """Model for a sent request event (before response arrives)."""

    timestamp: datetime
    cluster: str
    trace_id: str | None = None
    payload: Any | None = None
