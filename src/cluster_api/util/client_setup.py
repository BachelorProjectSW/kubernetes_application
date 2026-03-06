from kubernetes import client, config



def get_api_client():
<<<<<<< HEAD:src/cluster_api/util/client_setup.py
    """Return a CoreV1Api client from the auth folder."""
    config.load_kube_config()
=======
    """Return the client API based of the k3s.yaml.

    which should be manually put into the auth folder.
    """
>>>>>>> 2ac5e97 (ruff check):kubernetes/util/client_setup.py
    return client.CoreV1Api()
