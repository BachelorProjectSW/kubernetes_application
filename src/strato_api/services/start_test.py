import requests
from ...models.basemodels import *


def start_test(config: Config):
    """Start test to the global scheduler. Further this should run chron job ensure the next in queue begins"""
    
    url = "http://127.0.0.1:8020/start_test" #url should be to global scheduler

    response = requests.post(url, json=config.model_dump())

    return response.json()


def start_test_test():
    """Start test test"""
    test_config = Config(
        id="123",
        name="demo test",
        start=StartConfig(
            duration_time_s=1000,
            start_time="01/10/2021",
            simulated_country_code="PT"
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
                gpio_list=[21, 20, 16]
            ),
            ClusterConfig(
                name="pt",
                ip="127.0.0.1",
                port="8050",
                gpio_list=[21, 20, 16]
            )
        ]
    )
    return start_test(test_config)