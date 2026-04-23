from ..util.client_setup import get_api_client
def get_llama_pods_status():
    api_client = get_api_client()

    pods = api_client.list_namespaced_pod(
        namespace="default",
        label_selector="app=llama-server",
    ).items

    result = []

    for pod in pods:
        conditions = getattr(pod.status, "conditions", None) or []
        ready = any(
            condition.type == "Ready" and condition.status == "True"
            for condition in conditions
        )

        result.append(
            {
                "name": pod.metadata.name,
                "node": pod.spec.node_name,
                "phase": pod.status.phase,
                "ready": ready,
                "deletion_timestamp": (
                    pod.metadata.deletion_timestamp.isoformat()
                    if pod.metadata.deletion_timestamp
                    else None
                ),
                "pod_ip": pod.status.pod_ip,
            }
        )

    return result