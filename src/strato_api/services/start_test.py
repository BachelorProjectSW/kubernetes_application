import threading

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
stop_requested = False
current_config = None


def start_test(config: Config):
    """Validate config, mark test state, and start execution in a thread.

    This entrypoint first asks the global API to validate the incoming config.
    If valid, it stores shared test state and starts the long-running test flow
    in a daemon thread so the HTTP request can return immediately.

    Args:
        config: Full test configuration received from the caller.

    Returns:
        dict[str, str]: Confirmation message that the test was started.

    Raises:
        RuntimeError: If validation fails or a test is already running.

    """
    global test_running, stop_requested, current_config

    try:
        config.id = str(uuid.uuid4())

        # Sanity checks of the config entries
        ip = config.global_scheduler.ip
        port = config.global_scheduler.port
        response = requests.post(
            f"http://{ip}:{port}/validate_config",
            #model.dump = python dic
            json=config.model_dump(),
            timeout=180
        )
        response.raise_for_status()
        validation = response.json()
        #if valid == false, not false == true
        if not validation["valid"]:
            raise RuntimeError(f"Invalid config: {validation['errors']}")
    except Exception as e:
        raise RuntimeError(f"Validation failed: {str(e)}")

    # Only run one test at a time
    with test_state_lock:
        if test_running:
            raise RuntimeError("A test is already running. Stop the current test before starting a new one.")
        test_running = True
        stop_requested = False
        current_config = config

    # Run the test on a separate thread so the API stays responsive.
    # daemon= the thread will not keep the Python process alive. If the API shuts down, the test may be terminated abruptly.
    thread = threading.Thread(target=run_test, args=(config,), daemon=True, name="test-runner")
    thread.start()
    log.info("test.started_in_background", config_id=config.id, test_name=config.name)
    return {"message": f"{config.name} test started successfully"}


def run_test(config: Config):
    """Run the full test lifecycle in the background.

    The flow is: persist config, ask global API to start test orchestration,
    run the generated workload, then reset local state flags in ``finally``.

    Args:
        config: Active test configuration for this run.

    Returns:
        None: Logs outcomes and updates shared state.

    """
    global test_running, stop_requested, current_config
    try:
        set_current_config_id(config.id)
        save_config(config)
        log.info("test.begins", source="strato_api", config_id=config.id, test_name=config.name)

        # Forward start to global API, which configures all clusters.
        ip = config.global_scheduler.ip
        port = config.global_scheduler.port
        url = f"http://{ip}:{port}/start_test"

        log.info("test.forward_to_global", url=url)
        response = requests.post(url, json=config.model_dump(), timeout=180)
        response.raise_for_status()
        log.info("test.global_started", status_code=response.status_code)

        # This blocks inside the background thread until workload ends or stops.
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
        # Always reset shared flags so a new test can start cleanly.
        with test_state_lock:
            test_running = False
            stop_requested = False
            current_config = None


def should_stop_test() -> bool:
    """Return whether the current test run should stop.

    Returns:
        bool: ``True`` when a stop request has been issued.

    """
    with test_state_lock:
        return stop_requested


def stop_test():
    """Request stop for the currently running test.

    This sets a shared stop flag that is polled by the workload runner. It
    also notifies the global API to stop scheduler-side activity.

    Returns:
        dict[str, str]: Confirmation that stop was requested.

    Raises:
        RuntimeError: If no test is currently running.

    """
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
    """Notify global API to stop test-side scheduler activity.

    Args:
        ip: Global API host.
        port: Global API port.

    Returns:
        None: Emits logs for success or failure.

    """
    try:
        requests.post(f"http://{ip}:{port}/stop_test", timeout=300)
        log.info("test.global_stop_requested")
    except Exception as e:
        log.warning("test.global_stop_failed", error=str(e))


def start_test_test():
    """Start a predefined test configuration used for quick checks.

    Returns:
        dict[str, str]: Response from ``start_test``.

    """
    return start_test(get_test_config())


def get_test_status() -> dict:
    """Return the current local test-runner state.

    Returns:
        dict: Status payload with ``status`` and ``current_config_id``.

    """
    with test_state_lock:
        if not test_running:
            return {
                "status": "idle",
                "current_config_id": None,
            }

        if stop_requested:
            return {
                "status": "stopping",
                "current_config_id": current_config.id if current_config else None,
            }

        return {
            "status": "running",
            "current_config_id": current_config.id if current_config else None,
        }
