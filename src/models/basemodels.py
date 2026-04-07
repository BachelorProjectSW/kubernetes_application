from pydantic import BaseModel
from pydantic import BaseModel
from typing import Literal


# --- user input ---
class StartConfig(BaseModel):
    duration_time_s: int
    start_time: str 


class WeightsConfig(BaseModel):
    gco2: float
    cost: float


class PowerSchedulerConfig(BaseModel):
    timeout_s: int
    idle_time_for_turn_off_s: int


class LatencyConfig(BaseModel):
    max_ms: int


class WorkloadConfig(BaseModel):
    request_per_minute: int
    pattern: Literal["steady", "peaks"] 
    seed: int
    peakiness: int


# --- Advanced user input
class QuestionConfig(BaseModel):
    """Question class."""
    question: str
    max_output_tokens: int
    context_window: int

class WorkerNode(BaseModel):
    name: str
    ip: str
    status: Literal["on", "off", "turning_on", "turning_off"]
    gpio: int

class ClusterConfig(BaseModel):
    """Cluster class."""
    name: str
    ip: str
    port: str
    gpio_list: list[int]
    simulated_country_code: str
    llama_service_port: str


class ClusterInformation(BaseModel):
    """All information the clusters need."""
    cluster_config: ClusterConfig
    question_config: QuestionConfig
    worker_nodes: list[WorkerNode]

class GlobalSchedulerConfig(BaseModel):
    ip: str
    port: str


class StratoConfig(BaseModel):
    ip: str
    port: str

class Config(BaseModel):
    id: str
    name: str 
    start: StartConfig
    weights: WeightsConfig
    power_scheduler: PowerSchedulerConfig
    latency: LatencyConfig
    workload: WorkloadConfig
    question: QuestionConfig
    clusters: list[ClusterConfig]
    global_scheduler: GlobalSchedulerConfig
    strato: StratoConfig