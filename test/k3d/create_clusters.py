from utils import get_cluster_names, run_cmd

def create_clusters():
    clusters = get_cluster_names()
    
    try:
        run_cmd("k3d cluster delete -a")
    except Exception:
        pass

    for cluster_name in cluster_names:
        run_cmd(f"k3d cluster create --config test/k3d/cluster_configs/cluster-{cluster_name}.yaml")
        run_cmd(f"k3d kubeconfig get devcluster-{cluster_name} > src/cluster_api/auth/k3d-devcluster-{cluster_name}.yaml")
        run_cmd(f"k3d image import llama-server-arm64 -c devcluster-{cluster_name}")

if __name__ == "__main__":
    create_clusters()
