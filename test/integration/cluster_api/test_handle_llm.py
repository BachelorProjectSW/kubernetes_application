import requests
import pytest
from concurrent.futures import ThreadPoolExecutor

from ...k3d.cluster_configs.test_config import get_test_config


def _cluster_api_base_url() -> str:
    config = get_test_config()
    cluster = config.clusters[0]
    return f"http://{cluster.ip}:{cluster.port}"


def _post_or_skip(url: str, **kwargs):
    try:
        return requests.post(url, **kwargs)
    except requests.RequestException as e:
        pytest.skip(f"cluster API is not available: {e}")


@pytest.mark.integration
def test_handle_llm_request_dk_one_worker():
    """Send one request to the DK cluster API and verify that the first idle worker is chosen.

    This integration test calls the real `/handle_llm_request` endpoint on the DK cluster API.
    It verifies that the request succeeds and that the scheduler selects the first worker
    in name-sorted order when multiple workers are idle.
    """
    payload = {
        "question": "Describe the color violet in one short sentence.",
        "max_output_tokens": 32,
    }

    response = _post_or_skip(
        f"{_cluster_api_base_url()}/handle_llm_request",
        json=payload,
        timeout=120,
    )

    assert response.status_code == 200

    data = response.json()
    assert "worker_node" in data
    assert "llm_content" in data
    assert data["worker_node"]["name"] in {
        "k3d-devcluster-dk-agent-0",
    }


@pytest.mark.integration
def test_handle_llm_request_dk_uses_both_workers_when_requests_overlap():
    """Send 2 parallel requests and verify that both idle DK workers are used."""
    payload = {
        "question": "Write a medium-length response about the use of kubernetes.",
        "max_output_tokens": 64,
    }

    def send_request():
        response = _post_or_skip(
            f"{_cluster_api_base_url()}/handle_llm_request",
            json=payload,
            timeout=120,
        )
        assert response.status_code == 200
        return response.json()["worker_node"]["name"]

    with ThreadPoolExecutor(max_workers=2) as executor:  # 2 requests can be send in parallel
        # Sends 2 requests and stores the response in list features
        futures = [executor.submit(send_request) for _ in range(2)]
        results = [future.result() for future in futures]

    assert "k3d-devcluster-dk-agent-0" in results
    assert "k3d-devcluster-dk-agent-1" in results


@pytest.mark.integration
def test_handle_llm_request_dk_enters_queueing_when_requests_exceed_total_slots():
    """Send 10 parallel requests and verify that both DK workers are used and enter queueing.

    Since each worker can handle at most 4 active requests, sending 10 overlapping
    requests should force queueing on both workers.
    """
    payload = {
        "question": "Write a medium-length response about the use of kubernetes.",
        "max_output_tokens": 128,
    }

    def send_request():
        response = _post_or_skip(
            f"{_cluster_api_base_url()}/handle_llm_request",
            json=payload,
            timeout=180,
        )
        assert response.status_code == 200
        return response.json()

    with ThreadPoolExecutor(max_workers=10) as executor:
        # Sends 10 requests and stores the response in list features
        futures = [executor.submit(send_request) for _ in range(10)]
        results = [future.result() for future in futures]

    worker_names = [result["worker_node"]["name"] for result in results]

    # Both workers are used
    assert "k3d-devcluster-dk-agent-0" in worker_names
    assert "k3d-devcluster-dk-agent-1" in worker_names

    workers = {
        "k3d-devcluster-dk-agent-0",
        "k3d-devcluster-dk-agent-1",
    }

    for worker_name in workers:
        assert any(
            result["worker_node"]["name"] == worker_name
            and result["queued_requests_at_selection"] > 0
            for result in results
        )
