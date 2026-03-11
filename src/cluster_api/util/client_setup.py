from kubernetes import client, config
import os

KUBECONFIG = os.getenv("KUBECONFIG")
config.load_kube_config(KUBECONFIG)


def get_api_client():
    """Return the client API based of the k3s.yaml.

    which should be manually put into the auth folder.
    """
    return client.CoreV1Api()
