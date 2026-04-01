import requests


LLAMA_SERVICE_URL = "http://llama-service:8080"


def forward_llm_question(question: str, n_predict: int = 64) -> dict:
    """Forward a prompt to the llama service endpoint."""
    payload = {
        "prompt": question,
        "n_predict": n_predict,
    }

    try:
        response = requests.post(
            f"{LLAMA_SERVICE_URL}/completion",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        raise RuntimeError(f"Llama service returned HTTP error: {e}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to contact llama service: {e}") from e
