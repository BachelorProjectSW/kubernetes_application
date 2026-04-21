import asyncio
import time
import aiohttp
import json
import structlog
from .generator import generate_workload
from ....models.basemodels import QuestionConfig


log = structlog.get_logger()


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
    """Generate and execute scheduled HTTP requests against an endpoint."""
    request_timeout_s = 90
    # TODO setup logging matching for our output. Logs should be appended to a global log file.
    start_time = time.perf_counter()

    timestamps = generate_workload(
        duration_s=duration_s,
        rpm=rpm,
        pattern=pattern,
        seed=seed,
        peakiness=peakiness,
    )

    log.info(
        "workload.generated",
        request_count=len(timestamps),
        duration_s=duration_s,
        target=f"{host}{endpoint}",
        request_timeout_s=request_timeout_s,
    )

    timeout = aiohttp.ClientTimeout(total=request_timeout_s)
    async with aiohttp.ClientSession(base_url=host, timeout=timeout) as session:

        async def _send_request(ts: float):
            """Wait until the scheduled timestamp, then send the request."""
            delay = ts - (time.perf_counter() - start_time)
            if delay > 0:
                await asyncio.sleep(delay)

            try:
                payload_json = json.dumps(question.model_dump())
                headers = {"Content-Type": "application/json"}  # ensure FastAPI parses it

                async with session.post(endpoint, data=payload_json, headers=headers) as resp:
                    body = await resp.text()
                    log.info("workload.request_done", status=resp.status)
                    return {"ok": 200 <= resp.status < 300, "status": resp.status, "body": body}
            except asyncio.CancelledError:
                log.info("workload.request_cancelled")
                return {"ok": False, "error": "cancelled"}
            except asyncio.TimeoutError:
                log.warning("workload.request_timeout", timeout_s=request_timeout_s)
                return {"ok": False, "error": f"request timeout after {request_timeout_s}s"}
            except Exception as e:
                log.warning("workload.request_failed", error=str(e))
                return {"ok": False, "error": str(e)}

        # Schedule all requests
        tasks = [asyncio.create_task(_send_request(ts)) for ts in timestamps]

        while not all(t.done() for t in tasks):  # Keep looping while tasks are being schedueled
            if stop_check():  # If the user decided to stop (this calls the function)
                log.info("workload.stop_requested — cancelling all tasks")
                for t in tasks:  # Loop through every task. If it iss still running or waiting, cancel it.
                    if not t.done():
                        t.cancel()
                break
            await asyncio.sleep(0.5)  # Runs every 0.5 sec

        results = await asyncio.gather(*tasks, return_exceptions=True)

    results = [r for r in results if isinstance(r, dict)]
    success_count = sum(1 for r in results if r.get("ok"))
    failure_count = len(results) - success_count
    log.info("workload.completed", success=success_count, failure=failure_count)
    return results


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
    """Run workload executor."""
    return asyncio.run(
        execute_workload(host, endpoint, question, duration_s, rpm, pattern, seed, peakiness, stop_check)
    )
