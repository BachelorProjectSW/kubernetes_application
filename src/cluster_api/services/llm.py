import requests
from ...models.basemodels import QuestionConfig


def handle_llm(question: QuestionConfig):
    try:
        url = "http://llama-service:8080/completion"

        payload = {
            "prompt": question.question,
            "n_predict": question.max_output_tokens,
        }

        response = requests.post(
            url,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        raise RuntimeError(f"Llama service returned HTTP error: {e}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to contact llama service: {e}") from e