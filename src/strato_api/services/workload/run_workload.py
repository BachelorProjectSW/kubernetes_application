import asyncio
import time
import aiohttp
import json
from .generator import generate_workload
from ....models.basemodels import QuestionConfig


async def execute_workload(
    host: str,
    endpoint: str,
    question: QuestionConfig,
    duration_s: int,
    rpm: int,
    pattern: str,
    seed: int,
    peakiness: float,
):
    """Generate and execute scheduled HTTP requests against an endpoint."""
    # TODO setup logging matching for our output. Logs should be appended to a global log file.
    start_time = time.perf_counter()

    timestamps = generate_workload(
        duration_s=duration_s,
        rpm=rpm,
        pattern=pattern,
        seed=seed,
        peakiness=peakiness,
    )

    print(f"Generated {len(timestamps)} requests over {duration_s}s")
    print(f"Target: {host}{endpoint}")

    async with aiohttp.ClientSession(base_url=host) as session:

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
                    print(f"request.success status={resp.status} body={body}")
                    return {"ok": 200 <= resp.status < 300, "status": resp.status, "body": body}
            except Exception as e:
                print(f"request.failure error={e} ")
                return {"ok": False, "error": str(e)}

        # Schedule all requests
        tasks = [asyncio.create_task(_send_request(ts)) for ts in timestamps]
        results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r.get("ok"))
    failure_count = len(results) - success_count
    print(f"Completed requests: success={success_count}, failure={failure_count}")
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
):
    """Run workload executor."""
    return asyncio.run(
        execute_workload(host, endpoint, question, duration_s, rpm, pattern, seed, peakiness)
    )
