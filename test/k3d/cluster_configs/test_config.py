from datetime import datetime
import Op
from src.models.basemodels import (
    Config,
    StartConfig,
    WeightsConfig,
    PowerSchedulerConfig,
    LatencyConfig,
    WorkloadConfig,
    QuestionConfig,
    ClusterConfig,
    GlobalSchedulerConfig,
    StratoConfig,
)


def get_test_config():
    """Start test test."""
    test_config = Config(
        id="123",
        name="demo test",
        start=StartConfig(
            duration_time_s=30,
            start_time_simulated=datetime(2024, 5, 17, 14, 30, 0),
            start_time_real=None
        ),
        weights=WeightsConfig(
            gco2=0.1,
            cost=0.9
        ),
        power_scheduler=PowerSchedulerConfig(
            timeout_s=30,
            idle_time_for_turn_off_s=120
        ),
        latency=LatencyConfig(
            max_ms=12000
        ),
        workload=WorkloadConfig(
            request_per_minute=4,
            pattern="steady",
            seed=10,
            peakiness=0
        ),
        question=QuestionConfig(
            question="hey",
            max_output_tokens=200,
            context_window=200
        ),
        clusters=[
            ClusterConfig(
                name="dk",
                ip="127.0.0.1",
                port="8040",
                gpio_list=[21],
                simulated_country_code="dk-dk1",
                llama_service_port="8083",
                renewable_output_w=200,
                cluster_load_w=1000,
                grid_carbon_intensity=100,
                grid_electricity_price=0.12

            ),
            ClusterConfig(
                name="pt",
                ip="127.0.0.1",
                port="8050",
                gpio_list=[21],
                simulated_country_code="pt",
                llama_service_port="8082",
                renewable_output_w=400,
                cluster_load_w=1000,
                grid_carbon_intensity=300,
                grid_electricity_price=0.14
            ),
        ],
        global_scheduler=GlobalSchedulerConfig(
            ip="127.0.0.1",
            port="8020"
        ),
        strato=StratoConfig(
            ip="127.0.0.1",
            port="8090"
        )
    )
    return test_config
