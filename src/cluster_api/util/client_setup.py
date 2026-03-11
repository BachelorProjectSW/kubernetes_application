from kubernetes import client, config
import os

KUBECONFIG = os.getenv("KUBECONFIG")
config.load_kube_config(KUBECONFIG)


def get_api_client():
    """Return the client, which is inside the /auth folder."""
    return client.CoreV1Api()
