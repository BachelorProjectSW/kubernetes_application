import random
import requests
from ..util.cluster_connection import get_all_clusters_config

def choose_cluster():
    clusters = get_all_clusters_config()
    return random.choice(list(clusters.values()))    

def handle_llm_request(question: str):
    cluster = choose_cluster()
    llama_port = cluster["llama-service"]

    url = f"http://127.0.0.1:{llama_port}/v1/chat/completions" 

    payload = {
        "model": "model",
        "messages": [
            {"role": "user", "content": question}
        ],
        "temperature": 0.7,
        "max_tokens": 500  
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()  # Raises error for HTTP codes >= 400
        data = response.json()
        return data
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None
