import requests


def test_llama_service_models_endpoint():
    response = requests.get("http://127.0.0.1:8080/v1/models", timeout=15)
    assert response.status_code == 200