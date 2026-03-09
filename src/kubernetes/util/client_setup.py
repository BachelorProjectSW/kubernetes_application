from kubernetes import client, config

config.load_kube_config("auth/k3s.yaml")


def get_api_client():
    """Return the client API based of the k3s.yaml.

    which should be manually put into the auth folder.
    """
    return client.CoreV1Api()
