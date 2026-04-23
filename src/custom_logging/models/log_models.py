from pydantic import BaseModel
from datetime import datetime
from typing import Any


class RequestLog(BaseModel):
    """Model for a single completed request log entry."""

    request_id: str
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
    global_market_data_fetch_ms: int | None = None
    global_cluster_scoring_ms: int | None = None
    global_cluster_api_call_ms: int | None = None
    global_total_time_ms: int | None = None
    cluster_queue_time_ms: int | None = None
    cluster_llama_inference_ms: int | None = None


class PowerDecisionLog(BaseModel):
    """Model for a single power decision log entry."""

    timestamp: datetime
    action: str
    cluster: str
    node: str
    reason: str
    system_avg_latency_ms: float


class NodeStatusLog(BaseModel):
    """Status of a single node's status at a given timestamp."""

    timestamp: datetime
    cluster: str
    node: str
    status: str


class TerminalDebugLog(BaseModel):
    """Model for terminal debug entries stored in the database."""

    config_id: str | None
    message: str
    payload: dict | None = None
    created_at: datetime
