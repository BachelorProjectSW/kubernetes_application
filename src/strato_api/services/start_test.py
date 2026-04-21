import threading

import requests
from ...models.basemodels import Config
from ...db.postgres import save_config
from ...custom_logging.logger import set_current_config_id
from test.k3d.cluster_configs.test_config import get_test_config
from .workload.run_workload import run_workload
import structlog


log = structlog.get_logger()

test_state_lock = threading.Lock()
test_running = False
stop_requested = False
current_config: Config

def start_test(config: Config):
    """Start test in a background thread and return immediately."""
    global test_running, stop_requested, current_config

    with test_state_lock:
        if test_running:
            raise RuntimeError("A test is already running. Stop the current test before starting a new one.")
        test_running = True
        stop_requested = False
        current_config = config

    thread = threading.Thread(target=run_test, args=(config,), daemon=True, name="test-runner")
    thread.start()
    log.info("test.started_in_background", config_id=config.id, test_name=config.name)
    return {"message": f"{config.name} test started successfully"}

def run_test(config: Config):
    """Run the full test in a background thread."""
    global test_running, stop_requested, current_config
    try:
        set_current_config_id(config.id)
        save_config(config)
        log.info("test.begins", source="strato_api", config_id=config.id, test_name=config.name)

        ip = config.global_scheduler.ip
        port = config.global_scheduler.port

        log.info("test.forward_to_global", url=f"http://{ip}:{port}/start_test")
        response = requests.post(f"http://{ip}:{port}/start_test", json=config.model_dump(), timeout=180)
        response.raise_for_status()
        log.info("test.global_started", status_code=response.status_code)

        results = run_workload(
            f"http://{ip}:{port}",
            "/handle_llm_question",
            config.question,
            config.start.duration_time_s,
            config.workload.request_per_minute,
            config.workload.pattern,
            config.workload.seed,
            config.workload.peakiness,
            stop_check=should_stop_test,
        )

        if should_stop_test():
            log.info("test.stopped", responses=len(results))
        else:
            log.info("test.completed", responses=len(results))

    except Exception as e:
        log.exception("test.failed", error=str(e))
    finally:
        with test_state_lock:
            test_running = False
            stop_requested = False
            current_config = None

def should_stop_test() -> bool:
    """Return True if the running test should stop."""
    with test_state_lock:
        return stop_requested

def stop_test():
    global stop_requested
    with test_state_lock:
        if not test_running:
            raise RuntimeError("No test is currently running.")
        stop_requested = True
        config = current_config

    log.info("test.stop_requested")
    stop_global_power_scheduler(config.global_scheduler.ip, config.global_scheduler.port)
    return {"message": "Stop requested"}

def stop_global_power_scheduler(ip, port):
    """Tell global API to stop the power scheduler."""
    try:
        requests.post(f"http://{ip}:{port}/stop_test", timeout=60)
        log.info("test.global_stop_requested")
    except Exception as e:
        log.warning("test.global_stop_failed", error=str(e))

def start_test_test():
    """Start test test."""
    return start_test(get_test_config())