import random
import requests
from ..util.all_configuration import config_store
from ...models.basemodels import QuestionConfig
from .scoring import choose_cluster


def handle_llm_request(question: QuestionConfig):
    """Send the question to the local cluster request scheduler llama-service."""
    cluster = choose_cluster()
    ip = cluster.ip
    port = cluster.port
    url = f"http://{ip}:{port}/handle_llm_request"
    response = requests.post(url, json=question.model_dump())

    return response.json()
