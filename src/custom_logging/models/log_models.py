from pydantic import BaseModel
from datetime import datetime


class RequestLog(BaseModel):
    """Model for a single completed request log entry."""

    request_id: str
    timestamp: datetime
    strategy: str
    cluster: str
    node: str
    latency_ms: float


class PowerDecisionLog(BaseModel):
    """Model for a single power decision log entry."""

    timestamp: datetime
    action: str
    cluster: str
    node: str
    reason: str
    system_avg_latency_ms: float
