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
        id=None,
        name="k3d_test!",
        start=StartConfig(
            duration_time_s=60,
            start_time_simulated="25/03/2026 15:00:00",  # PT 0.645 (CROM LOW)
            start_time_real=None
        ),
        weights=WeightsConfig(
            gco2=0.9,
            cost=0.05,
            latency=0.05
        ),
        power_scheduler=PowerSchedulerConfig(
            start=False,
            timeout_s=10,
            idle_time_for_turn_off_s=20
        ),
        latency=LatencyConfig(
            latency_window_s=60,
            max_ms=20000
        ),
        workload=WorkloadConfig(
            request_per_minute=20,
            pattern="steady",
            seed=10,
            peakiness=0
        ),
        question=QuestionConfig(
            question="What is the best programming language?",
            max_output_tokens=30,
        ),
        clusters=[
            ClusterConfig(
                name="dk",
                ip="127.0.0.1",
                port="8073",
                gpio_list=[1, 2],
                simulated_country_code="DK",
                llama_service_port="8075",
                k3d=True
            ),
            ClusterConfig(
                name="pt",
                ip="127.0.0.1",
                port="8074",
                gpio_list=[1],
                simulated_country_code="PT",
                llama_service_port="8076",
                k3d=True
            ),
        ],
        global_scheduler=GlobalSchedulerConfig(
            ip="127.0.0.1",
            port="8072"
        ),
        strato=StratoConfig(
            ip="127.0.0.1",
            port="8071"
        )
    )
    return test_config
