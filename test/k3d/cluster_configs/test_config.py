from src.models.basemodels import *

def get_test_config():
    """Start test test"""
    test_config = Config(
        id="123",
        name="demo test",
        start=StartConfig(
            duration_time_s=1000,
            start_time="01/10/2021"    
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
            request_per_minute=10,
            pattern="steady",
            seed=10,
            peakiness=0
        ),
        question=QuestionConfig(
            question="What is kubernetes?",
            max_output_tokens=200,
            context_window=4000
        ),
        clusters=[
            ClusterConfig(
                name="dk",
                ip="127.0.0.1",
                port="8040",
                gpio_list=[21],
                simulated_country_code="dk-dk1",
                llama_service_port="8081"


            ),
            ClusterConfig(
                name="pt",
                ip="127.0.0.1",
                port="8050",
                gpio_list=[21],
                simulated_country_code="pt",
                llama_service_port="8082"
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