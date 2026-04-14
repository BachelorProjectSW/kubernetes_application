from pydantic import BaseModel
from datetime import datetime


class RequestLog(BaseModel):
    """Model for a single completed request log entry."""

    request_id: str
    timestamp: datetime
    cluster: str
    node: str
    success: bool
    latency_ms: float
    cluster_load_w: float
    renewable_fraction: float
    blended_carbon_gco2_per_kwh: float
    blended_cost_eur_per_kwh: float


class PowerDecisionLog(BaseModel):
    """Model for a single global power scheduler decision."""

    timestamp: datetime
    action: str
    cluster: str
    requested_nodes: int
    changed_nodes: int
    nodes: str
    reason: str
    success: bool
    status_code: int | None = None
    system_avg_latency_ms: float | None = None
    max_latency_ms: float | None = None
    current_rps: float | None = None
    current_active_nodes: int | None = None
    estimated_nodes_to_add: int | None = None
    idle_time_threshold_s: int | None = None
    error: str | None = None


class NodeStatusLog(BaseModel):
    """Status of a single node's status at a given timestamp."""

    timestamp: datetime
    cluster: str
    node: str
    status: str
    active_nodes: int
    idle_nodes: int
