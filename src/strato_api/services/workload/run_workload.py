import time
import requests
import json
from ....models.basemodels import QuestionConfig
from .generator import generate_workload

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
    """Run workload using synchronous requests."""
    print(question.question, question.context_window, question.max_output_tokens)
    payload_json = json.dumps(question.model_dump())
    headers = {"Content-Type": "application/json"}

    # Generate request timestamps
    timestamps = generate_workload(
        duration_s=duration_s,
        rpm=rpm,
        pattern=pattern,
        seed=seed,
        peakiness=peakiness,
    )

    print(f"Generated {len(timestamps)} requests over {duration_s}s")
    print(f"Target: {host}{endpoint}")

    start_time = time.perf_counter()
    results = []

    for ts in timestamps:
        # Wait until scheduled timestamp
        delay = ts - (time.perf_counter() - start_time)
        if delay > 0:
            time.sleep(delay)

        start = time.perf_counter()
        try:
            resp = requests.post(f"{host}{endpoint}", data=payload_json, headers=headers)
            latency = time.perf_counter() - start
            print(f"request.success status={resp.status_code} latency={latency:.4f}s body={resp.text}")
            results.append({"ok": 200 <= resp.status_code < 300, "status": resp.status_code, "body": resp.text})
        except Exception as e:
            latency = time.perf_counter() - start
            print(f"request.failure error={e} latency={latency:.4f}s")
            results.append({"ok": False, "error": str(e)})

    success_count = sum(1 for r in results if r.get("ok"))
    failure_count = len(results) - success_count
    print(f"Completed requests: success={success_count}, failure={failure_count}")
    return results