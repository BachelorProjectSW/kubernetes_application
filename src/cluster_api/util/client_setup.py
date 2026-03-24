from kubernetes import client, config

AUTH_PATH = "src/cluster_api/auth/cluster_auth.yaml"


def get_api_client():
    """Return a CoreV1Api client from the auth folder."""
    config.load_kube_config(config_file=AUTH_PATH)
    return client.CoreV1Api()
