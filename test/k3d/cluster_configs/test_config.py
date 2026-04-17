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
        id="first_full_run",
        name="first_end_to_end",
        start=StartConfig(
            duration_time_s=30,
            start_time_simulated="01/10/2021",
            start_time_real=None
        ),
        weights=WeightsConfig(
            gco2=0.3,
            cost=0.1,
            latency=0.6
        ),
        power_scheduler=PowerSchedulerConfig(
            start=True,
            timeout_s=5,
            idle_time_for_turn_off_s=1
        ),
        latency=LatencyConfig(
            latency_window_s=60,
            max_ms=12000
        ),
        workload=WorkloadConfig(
            request_per_minute=10,
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
                ip="100.114.88.102",
                port="8040",
                gpio_list=[17, 27, 23],
                simulated_country_code="ES",
                llama_service_port="8083",
                renewable_output_w=200,
                cluster_load_w=1000,
                grid_carbon_intensity=100,
                grid_electricity_price=0.12,
                k3d=False
            ),
            ClusterConfig(
                name="pt",
                ip="100.83.243.61",
                port="8040",
                gpio_list=[17, 27, 23],
                simulated_country_code="pt",
                llama_service_port="8082",
                renewable_output_w=400,
                cluster_load_w=1000,
                grid_carbon_intensity=300,
                grid_electricity_price=0.14,
                k3d=False
            ),
        ],
        global_scheduler=GlobalSchedulerConfig(
            ip="100.84.252.101",
            port="8020"
        ),
        strato=StratoConfig(
            ip="100.109.95.2",
            port="8090"
        )
    )
    return test_config
