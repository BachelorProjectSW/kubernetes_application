import os
from utils import get_test_cluster_config, run_cmd
import time


def deploy_clusters():
    """Deploy clusters."""
    cluster_names = get_test_cluster_config()['clusters']

    for cluster_name in cluster_names:
        kubeconfig = f"src/cluster_api/auth/k3d-devcluster-{cluster_name}.yaml"
        os.environ["KUBECONFIG"] = kubeconfig

        run_cmd("kubectl wait --for=condition=Ready nodes --all --timeout=120s")
        run_cmd("kubectl apply -f src/cluster_api/manifest/")
        for _ in range(3):
            time.sleep(10)
            run_cmd("kubectl get pods -o wide")

        run_cmd(
            "kubectl --kubeconfig src/cluster_api/auth/k3d-devcluster-dk.yaml "
            "logs -l name=llama-server --all-containers"
        )
        run_cmd("kubectl wait --for=condition=Ready pod -l name=llama-server --timeout=180s")


if __name__ == "__main__":
    deploy_clusters()
