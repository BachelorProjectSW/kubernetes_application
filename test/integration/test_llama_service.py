import requests

BASE_URL = "http://127.0.0.1:8888"


def test_llama_service_models_endpoint():
    """Test llama endpoint."""
    response = requests.get(f"{BASE_URL}/v1/models", timeout=15)
    assert response.status_code == 200


def test_llm_simple():
    """Testing the LLM with simple math prompt, and checking the returned value."""
    payload = {
        "model": "model",
        "messages": [
            {"role": "user", "content": "What is 2+2? Reply with just the number."}
        ],
        "temperature": 0,
        "max_tokens": 2,
    }

    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json=payload,
        timeout=60,
    )

    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    content = data["choices"][0]["message"]["content"].strip()
    assert content == "4"
