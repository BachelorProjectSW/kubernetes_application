import requests
from ...models.basemodels import QuestionConfig
from .scoring import choose_cluster
from ..util.all_configuration import config_store


def handle_llm_request(question: QuestionConfig):
    """Send the question to the local cluster request scheduler llama-service."""
    # TODO start logging timer.
    config = config_store.get()
    # TODO calculate the current simulated time (start_time_real - datetime.now() + start_time_simulated)
    # TODO get "current simulated times^" cost and energy and update config.clusters information.

    # TODO make a function to determine if the workernodes are active or idle in each cluster.
    # TODO ^active nodes and idle nodes for each cluster.
    cluster = choose_cluster(config.clusters, config.weights)
    ip = cluster.ip
    port = cluster.port
    url = f"http://{ip}:{port}/handle_llm_request"
    response = requests.post(url, json=question.model_dump())

    # TODO log calculate time from begin to finish (our definition of latency)
    return response.json()
