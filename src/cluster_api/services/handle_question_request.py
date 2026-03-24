import request
from ..util.cluster_connection import get_all_clusters_endpoint

def handle_question_request(question: str):
    """Handle question reqeust temp."""
    for cluster, endpoint in get_all_clusters_endpoint().items():
        url = f"http://{endpoint}/llm"
        response = requests.get(url, timeout=5)
        worker_nodes.extend(response.json())

    return worker_nodes

