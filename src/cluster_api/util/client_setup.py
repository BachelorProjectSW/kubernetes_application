from kubernetes import client, config
import os

AUTH_PATH = "src/cluster_api/auth"


def get_api_clients():
    """Return a list of CoreV1Api clients, one per kubeconfig in the auth folder."""
    clients = []

    for file_name in os.listdir(AUTH_PATH):
        if file_name.startswith(("k3d")):
            kubeconfig_path = os.path.join(AUTH_PATH, file_name)
            config.load_kube_config(config_file=kubeconfig_path)
            api_client = client.CoreV1Api()
            clients.append(api_client)

    return clients
