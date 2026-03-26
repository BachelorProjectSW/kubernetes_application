import asyncio
import time
import aiohttp

from generator import generate_workload


class WorkloadExecutor:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def run(self, timestamps, endpoint, payload):
        start_time = time.perf_counter()

        async with aiohttp.ClientSession(base_url=self.base_url) as session:
            tasks = [
                asyncio.create_task(
                    self._schedule_request(session, ts, start_time, endpoint, payload)
                )
                for ts in timestamps
            ]

            results = await asyncio.gather(*tasks)
            success_count = sum(1 for r in results if r and r.get("ok"))
            failure_count = len(results) - success_count
            print(f"Completed requests: success={success_count}, failure={failure_count}")

    async def _schedule_request(self, session, ts, start_time, endpoint, payload):
        now = time.perf_counter()
        delay = ts - (now - start_time)

        if delay > 0:
            await asyncio.sleep(delay)

        return await self._send_request(session, endpoint, payload)

    async def _send_request(self, session, endpoint, payload):
        start = time.perf_counter()

        try:
            async with session.post(endpoint, json=payload) as resp:
                body = await resp.text()
                latency = time.perf_counter() - start
                answer = body
                print(f"request.success status={resp.status} latency={latency:.4f}s answer={answer}")
                return {"ok": 200 <= resp.status < 300, "status": resp.status, "body": body}

        except Exception as e:
            latency = time.perf_counter() - start

            print(f"request.failure error={e} latency={latency:.4f}s")
            return {"ok": False, "error": str(e)}

# Simple configuration
HOST = "http://192.168.50.100:8020"
ENDPOINT = "/handle_llm_question"
PAYLOAD = {"question": "What is Kubernetes?"}

DURATION_S = 10
RPM = 10
PATTERN = "peaks"  # "steady" or "peaks"
SEED = 42
PEAKINESS = 0.5


async def main() -> None:
    timestamps = generate_workload(
        duration_s=DURATION_S,
        rpm=RPM,
        pattern=PATTERN,
        seed=SEED,
        peakiness=PEAKINESS,
    )

    print(f"Generated {len(timestamps)} requests over {DURATION_S}s")
    print(f"Target: {HOST}{ENDPOINT}")

    executor = WorkloadExecutor(HOST)
    await executor.run(timestamps, ENDPOINT, PAYLOAD)


if __name__ == "__main__":
    asyncio.run(main())
