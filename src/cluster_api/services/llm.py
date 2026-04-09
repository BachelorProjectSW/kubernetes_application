import requests
from ...models.basemodels import QuestionConfig, WorkerNode, LLMResponse
from ..util.cluster_config import config_store
# TODO add logging.
# TODO change worker node status


def choose_worker_node(worker_node_list: list[WorkerNode]) -> WorkerNode:
    """Temp."""
    worker_node = worker_node_list[0]  # find a better solution
    return worker_node


def handle_llm(question: QuestionConfig):
    """Send the request to the correct working node and log."""
    try:
        config = config_store.get()
        worker_node = choose_worker_node(config.worker_nodes)
        # url = "http://llama-service:8080/completion"
        url = f"http://localhost:{config.cluster_config.llama_service_port}/completion"
        payload = {
            "prompt": question.question,
            "n_predict": question.max_output_tokens,
            "temperature": 0
        }

        response = requests.post(
            url,
            json=payload,
            timeout=60,
        )

        response.raise_for_status()
        return LLMResponse(llm_content=response.json(), worker_node=worker_node)

    except Exception as e:
        return f"failed: {e}"
