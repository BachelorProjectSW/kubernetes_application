import os

from kubernetes import client, config


def get_api_client():
    """Create and return an authenticated Kubernetes CoreV1Api client.

    Attempts to load in-cluster credentials first. If not running inside a pod,
    falls back to loading kubeconfig from the KUBECONFIG environment variable.
    This allows the function to work seamlessly in both production (in-cluster)
    and development (local k3d) environments without code changes.

    Returns:
        kubernetes.client.CoreV1Api: An authenticated client for interacting with
            Kubernetes core API resources (pods, services, configmaps, etc.).

    Raises:
        RuntimeError: If in-cluster config fails AND KUBECONFIG environment
            variable is not set. Ensure KUBECONFIG points to a valid kubeconfig
            file when running outside a Kubernetes cluster.

    """
    try:
        config.load_incluster_config()
    except config.ConfigException:
        kubeconfig = os.environ.get("KUBECONFIG")
        if not kubeconfig:
            raise RuntimeError("KUBECONFIG is not set")
        config.load_kube_config(config_file=kubeconfig)

    return client.CoreV1Api()
