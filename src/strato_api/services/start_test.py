import threading
import time

import requests
import uuid
from ...models.basemodels import Config
from ...db.postgres import save_config
from ...custom_logging.logger import set_current_config_id
from test.k3d.cluster_configs.test_config import get_test_config
from .workload.run_workload import run_workload
import structlog


log = structlog.get_logger()

test_state_lock = threading.Lock()
test_running = False
current_config = None
stop_event = threading.Event()



def start_test(config: Config):
    """Start test.

    This endpoint only returns success after global API has accepted /start_test.
    The workload itself still runs in a background thread.
    """
    global test_running, current_config

    config.id = str(uuid.uuid4())

    # Validate config against global before reserving local test state
    for attempt in range(5):
        try:
            ip = config.global_scheduler.ip
            port = config.global_scheduler.port
            response = requests.post(
                f"http://{ip}:{port}/validate_config",
                json=config.model_dump(),
                timeout=60,
            )
            response.raise_for_status()
            validation = response.json()
            if not validation["valid"]:
                raise RuntimeError(f"Invalid config: {validation['errors']}")
            break
        except RuntimeError:
            raise
        except Exception as e:
            if attempt == 4:
                raise RuntimeError(f"Could not reach global cluster: {e}")
            log.info("test.validate_config.retrying", attempt=attempt)
            time.sleep(3)

    # Reserve local state so only one test can start
    with test_state_lock:
        if test_running:
            if stop_event.is_set():
                raise RuntimeError("Previous test is still stopping.")
            raise RuntimeError("A test is already running. Stop the current test before starting a new one.")
        test_running = True
        current_config = config
        stop_event.clear()

    try:
        set_current_config_id(config.id)
        

        log.info("test.begins", source="strato_api", config_id=config.id, test_name=config.name)

        ip = config.global_scheduler.ip
        port = config.global_scheduler.port
        url = f"http://{ip}:{port}/start_test"

        log.info("test.forward_to_global", url=url)
        response = requests.post(url, json=config.model_dump(), timeout=180)
        response.raise_for_status()
        log.info("test.global_started", status_code=response.status_code)
        save_config(config)

        # Global accepted. Now start workload in background.
        thread = threading.Thread(
            target=run_test_workload,
            args=(config,),
            daemon=True,
            name="test-runner",
        )
        thread.start()

        log.info("test.started_in_background", config_id=config.id, test_name=config.name)
        return {"message": f"{config.name} test started successfully"}

    except Exception:
        # Global did not accept start, so release local state again
        with test_state_lock:
            test_running = False
            current_config = None
            stop_event.clear()
        raise


def run_test_workload(config: Config):
    """Run only the workload phase in a background thread."""
    global test_running, current_config

    try:
        set_current_config_id(config.id)

        ip = config.global_scheduler.ip
        port = config.global_scheduler.port

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
            current_config = None
            stop_event.clear()

def should_stop_test() -> bool:
    """Return True if the running test should stop."""
    return stop_event.is_set()


def stop_test():
    """Stop the currently running test."""
    with test_state_lock:
        if not test_running:
            raise RuntimeError("No test is currently running.")
        config = current_config
        stop_event.set()

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


def get_test_status() -> dict:
    """Return current test status."""
    with test_state_lock:
        if not test_running:
            return {"status": "idle"}
        if stop_event.is_set():
            return {"status": "stopping"}
        return {"status": "running"}
