import requests
from ...models.basemodels import QuestionConfig, WorkerNode
from ..util.cluster_config import config_store
import httpx

def choose_worker_node(worker_node_list: list[WorkerNode]) -> WorkerNode:
    worker_node = worker_node_list[0] #find a better solution
    return worker_node

    

def handle_llm(question: QuestionConfig):
    config = config_store.get()

    url = f"http://localhost:{config.cluster_config.llama_service_port}/completion"

    payload = {
        "prompt": question.question,
        "n_predict": question.max_output_tokens,
        "temperature": 0
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload)
            return response.text
    except Exception as e:
        return f"failed: {e}"