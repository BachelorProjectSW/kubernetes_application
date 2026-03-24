import random
import requests
from ..util.cluster_connection import get_all_clusters_config

def handle_llm_request(question: str):
    clusters = get_all_clusters_config()
    cluster = random.choice(clusters) 

    ip = cluster["ip"]
    port = cluster["port"]
    llama_port = cluster["llama-service"]  

    url = f"http://{ip}:{llama_port}/llm_question" 

    payload = {"question": question}

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        return response.json()  
    except requests.RequestException as e:
        print(f"Error sending question to LLM: {e}")
        return {"error": str(e)}