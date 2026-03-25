from global_api.services.handle_llm_request import handle_llm_request


def test_multi_cluster_request():
    """Test endpoint from two clusters."""
    response = handle_llm_request("What is 2+2")
    assert response.status_code == 200
