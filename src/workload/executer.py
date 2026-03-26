import asyncio
import time
import aiohttp
import structlog

from models import Results, RequestResult

logger = structlog.get_logger()


class WorkloadExecutor:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def run(self, timestamps, endpoint, payload) -> Results:
        logger.info("workload.start", total_requests=len(timestamps))

        start_time = time.perf_counter()

        async with aiohttp.ClientSession(base_url=self.base_url) as session:
            tasks = [
                asyncio.create_task(
                    self._schedule_request(session, ts, start_time, endpoint, payload)
                )
                for ts in timestamps
            ]

            results = await asyncio.gather(*tasks)

        logger.info("workload.finished")
        return results

    async def _schedule_request(self, session, ts, start_time, endpoint, payload):
        now = time.perf_counter()
        delay = ts - (now - start_time)

        if delay > 0:
            await asyncio.sleep(delay)

        return await self._send_request(session, endpoint, payload)

    async def _send_request(self, session, endpoint, payload) -> RequestResult:
        start = time.perf_counter()

        try:
            async with session.post(endpoint, json=payload) as resp:
                await resp.text()
                latency = time.perf_counter() - start

                logger.info(
                    "request.success",
                    status=resp.status,
                    latency=latency,
                )

                return RequestResult(True, latency)

        except Exception as e:
            latency = time.perf_counter() - start

            logger.error(
                "request.failure",
                error=str(e),
                latency=latency,
            )

            return RequestResult(False, latency)
