import requests
from ...models.basemodels import QuestionConfig, WorkerNode
from ..util.cluster_config import config_store

def choose_worker_node(worker_node_list: list[WorkerNode]) -> WorkerNode:
    worker_node = worker_node_list[0] #find a better solution
    return worker_node

def handle_llm(question: QuestionConfig):
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
            stream=True  # 👈 IMPORTANT
        )

        response.raise_for_status()

        try:
            return response.json()
        except Exception:
            # fallback: read raw text
            text = response.text
            print("RAW RESPONSE:", text)
            return {"raw": text}
    except Exception as e:
        return f"failed: {e}"