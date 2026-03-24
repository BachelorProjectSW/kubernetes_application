import requests

def handle_question_request(question: str):
    """Send a question to the local chat completions endpoint."""
    port = "8888"
    url = f"http://127.0.0.1:{port}/v1/chat/completions" 

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

