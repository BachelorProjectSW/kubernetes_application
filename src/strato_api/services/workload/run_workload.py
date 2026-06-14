import asyncio
import time
import aiohttp
import json
import requests
import structlog
import uuid
from aiohttp import ClientConnectorError
from .generator import generate_workload
from ....custom_logging.logger import log_request, log_sent
from ....models.basemodels import QuestionConfig


log = structlog.get_logger()


# Retry delays
RETRY_DELAY_S = 2
MAX_RETRIES = 2


async def execute_workload(
    host: str,
    endpoint: str,
    question: QuestionConfig,
    duration_s: int,
    rpm: int,
    pattern: str,
    seed: int,
    peakiness: float,
    stop_check,
):
    """Generate and execute a timed HTTP workload against a target endpoint.

    The function builds a request schedule using workload settings, sends each
    request close to its planned timestamp, and collects per-request success or
    failure results.

    Args:
        host: Base URL of the target API.
        endpoint: Relative endpoint path used for each request.
        question: Question payload sent to the endpoint.
        duration_s: Total workload duration in seconds.
        rpm: Target requests per minute.
        pattern: Workload shape (steady or peaks).
        seed: Seed used to make generated schedules reproducible.
        peakiness: Controls burst intensity for peak-based patterns.
        stop_check: Callable that returns ``True`` when execution should stop.

    Returns:
        list[dict]: Per-request result objects containing status or error info.

    """
    request_timeout_s = 1000
    start_time = time.perf_counter()

    timestamps = generate_workload(
        duration_s=duration_s,
        rpm=rpm,
        pattern=pattern,
        seed=seed,
        peakiness=peakiness,
    )

    log.info(
        "strato.workload.generated",
        request_count=len(timestamps),
        duration_s=duration_s,
        target=f"{host}{endpoint}",
        request_timeout_s=request_timeout_s,
    )

    # A fresh TCP connection must be established within 3 seconds.
    timeout = aiohttp.ClientTimeout(total=request_timeout_s, sock_connect=3)

    # Use a new TCP connection for each request instead of many
    # requests sharing the same aiohttp keep-alive connection pool.
    connector = aiohttp.TCPConnector(force_close=True)

    async with aiohttp.ClientSession(base_url=host, timeout=timeout, connector=connector) as session:

        async def _send_request(ts: float):
            """Send one request at its scheduled offset from workload start.

            Args:
                ts: Scheduled offset in seconds from ``start_time``.

            Returns:
                dict: Result payload with ``ok`` flag and response/error data.

            """
            # Translate the schedule offset into a sleep relative to "now".
            delay = ts - (time.perf_counter() - start_time)
            if delay > 0:
                await asyncio.sleep(delay)

            request_reached_host = False
            try:
                trace_id = str(uuid.uuid4())
                request_start = time.perf_counter()
                payload_json = json.dumps(question.model_dump())
                headers = {
                    "Content-Type": "application/json",
                    "X-Trace-Id": trace_id,
                }

                log.debug(
                    "strato.workload.request_started",
                    trace_id=trace_id,
                    target=f"{host}{endpoint}",
                )

                # Record that this request is being sent (used by global power scheduler for RPS)
                try:
                    log_sent(host, trace_id=trace_id, payload={"question": question.question})
                except Exception:
                    pass

                for attempt in range(MAX_RETRIES + 1):
                    try:
                        async with session.post(endpoint, data=payload_json, headers=headers) as resp:
                            request_reached_host = True
                            body = await resp.text()
                            duration_ms = int((time.perf_counter() - request_start) * 1000)
                            log.debug(
                                "strato.workload.request_completed",
                                trace_id=trace_id,
                                status_code=resp.status,
                                duration_ms=duration_ms,
                            )
                            return {"ok": 200 <= resp.status < 300,
                                    "status": resp.status, "body": body}
                    except (asyncio.TimeoutError, ClientConnectorError):

                        #Retry only connection failures. If a response was already received,
                        #do not retry because the server may have processed the POST.
                        if request_reached_host or attempt == MAX_RETRIES:
                            raise
                        log.debug(
                            "strato.workload.retry_connect_failed",
                            trace_id=trace_id,
                            attempt=attempt,
                        )
                        await asyncio.sleep(RETRY_DELAY_S)
            except asyncio.CancelledError:
                log.info("workload.request_cancelled")
                return {"ok": False, "error": "cancelled"}
            except asyncio.TimeoutError:
                duration_ms = int((time.perf_counter() - request_start) * 1000)
                if not request_reached_host:
                    log_request(
                        cluster_name="unknown",
                        worker_node_name="unknown",
                        success=False,
                        latency_ms=duration_ms,
                        cluster_load_w=0,
                        renewable_fraction=0,
                        blended_carbon_gco2_per_kwh=0,
                        blended_cost_eur_per_kwh=0,
                        question=question.question,
                        answer="unknown",
                        response_status_code=None,
                        all_content={
                            "error_type": "asyncio.TimeoutError",
                            "error": f"connect timed out after {duration_ms}ms",
                            "request_reached_host": False,
                        },
                        trace_id=trace_id,
                    )
                log.warning(
                    "strato.workload.request_timeout",
                    trace_id=trace_id,
                    timeout_s=request_timeout_s,
                    duration_ms=duration_ms,
                )
                return {"ok": False, "error": f"request timeout after {request_timeout_s}s"}
            except Exception as e:
                duration_ms = int((time.perf_counter() - request_start) * 1000)
                if not request_reached_host:
                    log_request(
                        cluster_name="unknown",
                        worker_node_name="unknown",
                        success=False,
                        latency_ms=duration_ms,
                        cluster_load_w=0,
                        renewable_fraction=0,
                        blended_carbon_gco2_per_kwh=0,
                        blended_cost_eur_per_kwh=0,
                        question=question.question,
                        answer="unknown",
                        response_status_code=None,
                        all_content={
                            "error_type": type(e).__name__,
                            "error": str(e),
                            "request_reached_host": False,
                        },
                        trace_id=trace_id,
                    )
                log.warning(
                    "strato.workload.request_failed",
                    trace_id=trace_id,
                    error_type=type(e).__name__,
                    error=str(e),
                    duration_ms=duration_ms,
                )
                return {"ok": False, "error": str(e)}

        # Create one async task per planned request timestamp.
        tasks = [asyncio.create_task(_send_request(ts)) for ts in timestamps]

        # Poll for completion so we can react quickly to external stop requests.
        while not all(t.done() for t in tasks):
            if stop_check():
                log.info("workload.stop_requested - cancelling all tasks")
                # Cancel tasks that are still waiting or running.
                for t in tasks:
                    if not t.done():
                        t.cancel()
                break
            await asyncio.sleep(0.5)

        results = await asyncio.gather(*tasks, return_exceptions=True)

    results = [r for r in results if isinstance(r, dict)]
    success_count = sum(1 for r in results if r.get("ok"))
    failure_count = len(results) - success_count
    log.info("strato.workload.completed", success_count=success_count, failure_count=failure_count)
    return results


def _stop_global_test(host: str):
    """Request global test shutdown after workload execution completes.

    Args:
        host: Base URL of the global API.

    Returns:
        None: Emits logs for success/failure of the stop request.

    """
    try:
        response = requests.post(f"{host}/stop_test", timeout=500)
        response.raise_for_status()
        log.info("strato.workload.global_stop_requested", status_code=response.status_code)
    except Exception as e:
        log.warning("strato.workload.global_stop_failed", error=str(e))


def run_workload(
    host: str,
    endpoint: str,
    question: QuestionConfig,
    duration_s: int,
    rpm: int,
    pattern: str,
    seed: int,
    peakiness: float,
    stop_check
):
    """Run workload execution in a synchronous entrypoint.

    This wrapper bridges sync callers to the async workload engine and ensures
    a global stop request is sent in a ``finally`` block.

    Args:
        host: Base URL of the target/global API.
        endpoint: Relative endpoint path used for workload requests.
        question: Question payload sent per generated request.
        duration_s: Total workload duration in seconds.
        rpm: Target requests per minute.
        pattern: Workload shape (for example, steady or peaks).
        seed: Seed used to make generated schedules reproducible.
        peakiness: Controls burst intensity for peak-based patterns.
        stop_check: Callable that returns ``True`` when execution should stop.

    Returns:
        list[dict]: Per-request result objects returned by ``execute_workload``.

    """
    try:
        return asyncio.run(
            execute_workload(host, endpoint, question, duration_s, rpm, pattern, seed, peakiness, stop_check)
        )
    finally:
        _stop_global_test(host)
