import requests
from ...models.basemodels import QuestionConfig
from .scoring import choose_cluster
from ..util.all_configuration import config_store


def handle_llm_request(question: QuestionConfig):
    """Send the question to the local cluster request scheduler llama-service."""
    config = config_store.get()
    #TODO call API for cluster cost and energy data. 
    cluster = choose_cluster(config.clusters, config.weights)
    ip = cluster.ip
    port = cluster.port
    url = f"http://{ip}:{port}/handle_llm_request"
    response = requests.post(url, json=question.model_dump())

    return response.json()
