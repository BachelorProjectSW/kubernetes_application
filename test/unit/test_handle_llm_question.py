from unittest.mock import Mock, patch
import pytest
import requests
from cluster_api.services.forward_llm_question import forward_llm_question

@patch("cluster_api.services.forward_llm_question.requests.post")
def test_forward_llm_question_success(mock_post):
    mock_response = Mock()
    mock_response.json.return_value = {"content": "Hello there"}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = forward_llm_question("Say hello", 64)

    assert result == {"content": "Hello there"}
    mock_post.assert_called_once_with(
        "http://llama-service:8080/completion",
        json={"prompt": "Say hello", "n_predict": 64},
        timeout=60,
    )

@patch("cluster_api.services.forward_llm_question.requests.post")
def test_forward_llm_question_http_error(mock_post):
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    mock_post.return_value = mock_response

    with pytest.raises(RuntimeError, match="Llama service returned HTTP error"):
        forward_llm_question("Say hello", 64)


@patch("cluster_api.services.forward_llm_question.requests.post")
def test_forward_llm_question_request_error(mock_post):
    mock_post.side_effect = requests.RequestException("Connection failed")

    with pytest.raises(RuntimeError, match="Failed to contact llama service"):
        forward_llm_question("Say hello", 64)

