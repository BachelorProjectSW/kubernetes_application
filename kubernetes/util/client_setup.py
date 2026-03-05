from kubernetes import client, config

config.load_kube_config("config/k3s.yaml")

def get_api_client():
    return client.CoreV1Api()
