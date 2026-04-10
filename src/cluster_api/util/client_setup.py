import os

from kubernetes import client, config


def get_api_client():
    """Return a CoreV1Api client from the auth folder."""
    try:
        config.load_incluster_config()  # NOT TESTED
    except config.ConfigException:
        kubeconfig = os.environ.get("KUBECONFIG")
        if not kubeconfig:
            raise RuntimeError("KUBECONFIG is not set")
        config.load_kube_config(config_file=kubeconfig)

    return client.CoreV1Api()
