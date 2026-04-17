from pydantic import BaseModel
from typing import Literal
from .enum import WorkerStatus


# --- user input ---
class StartConfig(BaseModel):
    """Basic."""

    duration_time_s: int
    start_time_simulated: str
    start_time_real: str | None = None


class WeightsConfig(BaseModel):
    """Weights."""

    gco2: float
    cost: float
    latency: float


class PowerSchedulerConfig(BaseModel):
    """Power Scheduler inputs."""

    start: bool  # Should it run or not
    timeout_s: int
    idle_time_for_turn_off_s: int


class LatencyConfig(BaseModel):
    """Max Latency pr request."""
    latency_window_s: int
    max_ms: int


class WorkloadConfig(BaseModel):
    """Workload."""

    request_per_minute: int
    pattern: Literal["steady", "peaks"]
    seed: int
    peakiness: int


# --- Advanced user input
class QuestionConfig(BaseModel):
    """Question class."""

    question: str  # TODO make it a list of question and add x new questions
    max_output_tokens: int
    context_window: int


class WorkerNode(BaseModel):
    """Worker Node."""

    name: str
    ip: str
    status: WorkerStatus
    inflight_requests: int = 0
    max_slots: int = 0
    gpio: int
    forwarded_port: int | None = None

    @property
    def active_requests(self) -> int:
        """Number of requests actively occupying slots."""
        return min(self.inflight_requests, self.max_slots)

    @property
    def queued_requests(self) -> int:
        """Number of requests beyond slot capacity."""
        return max(0, self.inflight_requests - self.max_slots)

    @property
    def free_slots(self) -> int:
        """Number of currently free slots."""
        return max(0, self.max_slots - self.active_requests)


class ClusterConfig(BaseModel):
    """Cluster class."""

    name: str
    ip: str
    port: str
    gpio_list: list[int]
    simulated_country_code: str
    k3d: bool = False
    llama_service_port: int | None = None
    llama_hostport: int = 8080


class ClusterRuntimeData(BaseModel):
    """Runtime energy data for a cluster at a given point in time."""

    renewable_output_w: float
    cluster_load_w: float
    grid_carbon_intensity: float
    grid_electricity_price: float
    avg_latency_ms: float


class ClusterInformation(BaseModel):
    """All information the clusters need."""

    cluster_config: ClusterConfig
    question_config: QuestionConfig
    worker_nodes: list[WorkerNode]


class GlobalSchedulerConfig(BaseModel):
    """Global."""

    ip: str
    port: str


class StratoConfig(BaseModel):
    """Frontend."""

    ip: str
    port: str


class EnergyConfig(BaseModel):
    """Energy consumption and scoring normalization constants."""

    # Power consumption per node (watts)
    node_power_off_w: float = 0
    node_power_idle_w: float = 5
    node_power_active_w: float = 8

    # How many nanos each nano is scaled up to
    power_scale_factor: int = 50

    # Capacity of PV installation per cluster (watts)
    pv_capacity_w: float = 1500

    # Reference maximums for scoring normalization
    carbon_ref_max: float = 800  # gCO2/kWh
    cost_ref_max: float = 0.30  # EUR/kWh


class Config(BaseModel):
    """Config."""

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
    energy: EnergyConfig = EnergyConfig()


class LLMResponse(BaseModel):
    """LLM response."""

    llm_content: dict
    worker_node: WorkerNode
    inflight_requests_at_selection: int
    active_requests_at_selection: int
    queued_requests_at_selection: int
    max_slots: int
