import os
from utils import get_cluster_names, run_cmd


def deploy_clusters():
    """Deploy clusters."""
    cluster_names = get_cluster_names()

    for cluster_name in cluster_names:
        kubeconfig = f"src/cluster_api/auth/k3d-devcluster-{cluster_name}.yaml"
        os.environ["KUBECONFIG"] = kubeconfig

        run_cmd("kubectl wait --for=condition=Ready nodes --all --timeout=120s")
        run_cmd("kubectl apply -f src/cluster_api/manifest/")
        run_cmd("kubectl apply -f src/cluster_api/manifest/test")
        run_cmd("kubectl wait --for=condition=Ready pod -l name=llama-server --timeout=180s")


if __name__ == "__main__":
    deploy_clusters()
