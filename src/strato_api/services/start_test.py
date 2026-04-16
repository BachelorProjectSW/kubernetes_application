import requests
from ...models.basemodels import Config
from ...db.postgres import save_config
from test.k3d.cluster_configs.test_config import get_test_config
from .workload.run_workload import run_workload


def start_test(config: Config):
    """Start test to the global scheduler."""
    save_config(config)
    # TODO setup current status, to ensure multiple test runs are running at the same time.
    ip = config.global_scheduler.ip
    port = config.global_scheduler.port
    url = f"http://{ip}:{port}/start_test"  # url should be to global scheduler

    response = requests.post(url, json=config.model_dump(), timeout=60)
    response.raise_for_status()

    host = f"http://{config.global_scheduler.ip}:{config.global_scheduler.port}"
    results = run_workload(
        host,
        "/handle_llm_question",
        config.question,
        config.start.duration_time_s,
        config.workload.request_per_minute,
        config.workload.pattern,
        config.workload.seed,
        config.workload.peakiness
        )
    return f"Got {len(results)} responses"
    # TODO return analysed logs to frontend.


def start_test_test():
    """Start test test."""
    return start_test(get_test_config())
