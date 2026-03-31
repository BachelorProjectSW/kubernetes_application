from kubernetes import client, config


def get_api_client():
    """Return a CoreV1Api client from the auth folder."""
    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.CoreV1Api()
