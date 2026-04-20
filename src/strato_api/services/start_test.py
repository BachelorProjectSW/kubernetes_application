import threading

import requests
from ...models.basemodels import Config
from ...db.postgres import save_config
from test.k3d.cluster_configs.test_config import get_test_config
from .workload.run_workload import run_workload
import structlog


log = structlog.get_logger()

test_state_lock = threading.Lock()
test_running = False
stop_requested = False

def start_test(config: Config):
    """Start test to the global scheduler."""
    global test_running, stop_requested

    with test_state_lock:
        if test_running:
            raise RuntimeError(
                "A test is already running. Stop the current test before starting a new one."
            )
        test_running = True
        stop_requested = False

    try:
        save_config(config)
        log.info(
            "test.begins",
            source="strato_api",
            config_id=config.id,
            test_name=config.name,
        )
        # TODO setup current status, to ensure multiple test runs are running at the same time.
        ip = config.global_scheduler.ip
        port = config.global_scheduler.port
        url = f"http://{ip}:{port}/start_test"  # url should be to global scheduler

        log.info("test.forward_to_global", url=url)
        response = requests.post(url, json=config.model_dump(), timeout=60)
        response.raise_for_status()
        log.info("test.global_started", status_code=response.status_code)

        host = f"http://{config.global_scheduler.ip}:{config.global_scheduler.port}"
        results = run_workload(
            host,
            "/handle_llm_question",
            config.question,
            config.start.duration_time_s,
            config.workload.request_per_minute,
            config.workload.pattern,
            config.workload.seed,
            config.workload.peakiness,
            stop_check=should_stop_test,
            )

        stopped = should_stop_test()
        url = f"http://{ip}:{port}/stop_test"
        if stopped:
            requests.post(url, json=config.model_dump(), timeout=60)
            log.info("test.stopped", responses=len(results))
            return f"Test stopped early. Got {len(results)} responses"


        log.info("test.completed", responses=len(results))
        return f"Got {len(results)} responses"
        # TODO return analysed logs to frontend.
    finally:
            with test_state_lock:
                test_running = False
                stop_requested = False

def start_test_test():
    """Start test test."""
    return start_test(get_test_config())

def should_stop_test() -> bool:
    """Return True if the running test should stop."""
    with test_state_lock:
        return stop_requested

def stop_test():
    """Request the currently running test to stop."""
    global stop_requested

    with test_state_lock:
        if not test_running:
            raise RuntimeError("No test is currently running.")
        stop_requested = True

    log.info("test.stop_requested")

    return {"message": "Stop requested"}