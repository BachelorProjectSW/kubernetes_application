from kubernetes import client, config
import os

KUBE_CONFIG_PATH = os.getenv("KUBE_CONFIG_PATH","src/cluster_api/auth/k3s.yaml")
config.load_kube_config(KUBE_CONFIG_PATH)


def get_api_client():
    """Return the client API based of the k3s.yaml.

    which should be manually put into the auth folder.
    """
    return client.CoreV1Api()
