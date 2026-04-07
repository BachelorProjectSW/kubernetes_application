import glob
import os
from utils import get_test_cluster_config, run_cmd


def deploy_clusters():
    """Deploy clusters."""
    cluster_names = get_test_cluster_config()['clusters']

    manifest_files = sorted(glob.glob("src/cluster_api/manifest/all_*"))

    if not manifest_files:
        raise FileNotFoundError("No files matched src/cluster_api/manifest/all_*")

    for cluster_name in cluster_names:
        kubeconfig = f"src/cluster_api/auth/k3d-devcluster-{cluster_name}.yaml"
        os.environ["KUBECONFIG"] = kubeconfig

        run_cmd("kubectl wait --for=condition=Ready nodes --all --timeout=120s")
        for manifest in manifest_files:
            run_cmd(["kubectl", "apply", "-f", manifest])
        run_cmd("kubectl wait --for=condition=Ready pod -l name=llama-server --timeout=180s")
        run_cmd("kubectl get svc llama-service")
        run_cmd("kubectl wait --for=jsonpath='{.subsets[0].addresses[0].ip}' "
        "endpoints/llama-service --timeout=180s")


if __name__ == "__main__":
    deploy_clusters()
