import requests
import pytest
from concurrent.futures import ThreadPoolExecutor


BASE_URL = "http://127.0.0.1:8040/handle_llm_request"


def _post(payload: dict, timeout: int = 120) -> dict:
    """Helper to send a request and return parsed JSON."""
    response = requests.post(BASE_URL, json=payload, timeout=timeout)

    assert response.status_code == 200, f"Unexpected status: {response.text}"

    data = response.json()

    # Common structure validation
    assert isinstance(data, dict)
    assert "worker_name" in data
    assert "response" in data

    return data


@pytest.mark.integration
def test_single_request_uses_first_idle_worker():
    """
    When only one request is sent, the first idle worker
    (sorted by name) should be selected.
    """
    payload = {
        "question": "Describe the color violet in one short sentence.",
        "max_output_tokens": 32,
        "context_window": 256,
    }

    data = _post(payload)

    assert data["worker_name"] == "k3d-devcluster-dk-agent-0"
    assert data["response"] is not None


@pytest.mark.integration
def test_two_parallel_requests_use_both_workers():
    """
    When two requests are sent in parallel, both workers should be used.
    """
    payload = {
        "question": "Write a medium-length response about Kubernetes.",
        "max_output_tokens": 64,
        "context_window": 256,
    }

    def send_request():
        return _post(payload)["worker_name"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(send_request) for _ in range(2)]
        results = [f.result() for f in futures]

    assert "k3d-devcluster-dk-agent-0" in results
    assert "k3d-devcluster-dk-agent-1" in results


@pytest.mark.integration
def test_queueing_when_requests_exceed_capacity():
    """
    When more requests are sent than total available slots,
    both workers should be used and some requests should be queued.
    """
    payload = {
        "question": "Write a medium-length response about Kubernetes.",
        "max_output_tokens": 128,
        "context_window": 256,
    }

    def send_request():
        return _post(payload, timeout=180)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_request) for _ in range(10)]
        results = [f.result() for f in futures]

    worker_names = [r["worker_name"] for r in results]

    # Both workers must be used
    assert "k3d-devcluster-dk-agent-0" in worker_names
    assert "k3d-devcluster-dk-agent-1" in worker_names

    # At least one request per worker must have been queued
    for worker in {"k3d-devcluster-dk-agent-0", "k3d-devcluster-dk-agent-1"}:
        assert any(
            r["worker_name"] == worker
            and r.get("queued_requests_at_selection", 0) > 0
            for r in results
        ), f"No queued requests observed for {worker}"