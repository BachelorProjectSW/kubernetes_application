import random
import requests
from ..util.all_configuration import config_store


def choose_cluster():
    """Choose cluster is temp."""
    clusters = config_store.get_clusters()
    return random.choice(clusters)


def handle_llm_request(question: str):
    """Send the question to the local cluster request scheduler llama-service."""
    cluster = choose_cluster()
    ip = cluster.ip
    port = cluster.port
    url = f"http://{ip}:{port}/handle_llm_request"

    response = requests.post(url, json={"question": question})

    return response.json()