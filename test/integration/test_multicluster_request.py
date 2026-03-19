import requests

DK_CLUSTER_URL = "http://127.0.0.1:8888"
PO_CLUSTER_URL = "http://127.0.0.1:8889"


def test_multi_cluster_request():
    """Test endpoint from two clusters."""
    dk_response = requests.get(f"{DK_CLUSTER_URL}/v1/models", timeout=15)
    po_response = requests.get(f"{PO_CLUSTER_URL}/v1/models", timeout=15)
    assert dk_response.status_code == 200
    assert po_response.status_code == 200
