from pydantic import BaseModel
from typing import Literal


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


class PowerSchedulerConfig(BaseModel):
    """Power Scheduler inputs."""

    timeout_s: int
    idle_time_for_turn_off_s: int


class LatencyConfig(BaseModel):
    """Max Latency pr request."""

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
    status: Literal["off", "turning_on", "turning_off", "working", "idle"]
    gpio: int


class ClusterConfig(BaseModel):
    """Cluster class."""

    name: str
    ip: str
    port: str
    gpio_list: list[int]
    simulated_country_code: str
    llama_service_port: str
    renewable_output_w: float
    cluster_load_w: float
    grid_carbon_intensity: float
    grid_electricity_price: float


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
