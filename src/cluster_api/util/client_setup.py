from kubernetes import client, config


def get_api_client():
    """Return a CoreV1Api client from the auth folder."""
    config.load_kube_config()
    return client.CoreV1Api()
