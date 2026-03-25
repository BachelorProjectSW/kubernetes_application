from global_api.services.handle_llm_request import handle_llm_request


def test_multi_cluster_request():
    """Test endpoint from two clusters."""
    response = handle_llm_request("Descripe kubernetes")

    content = response["choices"][0]["message"]["content"]

    assert response
    assert content
