import os
import sys
from pathlib import Path
from multiprocessing import Process
import uvicorn
from utils import get_test_cluster_config, run_cmd_bg

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"


# Ensure child processes can import the top-level src package regardless of launch cwd.
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def run_global_server(port):
    """Run Global server."""
    uvicorn.run("src.global_api.app:app", host="0.0.0.0", port=port)


def run_cluster_server(cluster_name, port):
    """Run cluster server."""
    kubeconfig = SRC_DIR / "cluster_api" / "auth" / f"k3d-devcluster-{cluster_name}.yaml"
    os.environ["KUBECONFIG"] = str(kubeconfig)
    uvicorn.run("src.cluster_api.app:app", host="0.0.0.0", port=port)


def run_port_forward(cluster_name, local_port, service_port):
    """Start kubectl port-forward for the llama-service."""
    service_name = "llama-service"
    kubeconfig = SRC_DIR / "cluster_api" / "auth" / f"k3d-devcluster-{cluster_name}.yaml"
    cmd = [
        "kubectl",
        "--kubeconfig", str(kubeconfig),
        "port-forward",
        f"services/{service_name}",
        f"{local_port}:{service_port}"
    ]
    run_cmd_bg(cmd)


def start_all_servers():
    """Start global scheduler, all cluster control planes, and port-forward the llama-services."""
    cluster_config = get_test_cluster_config()
    server_processes = []

    # Start the global scheduler API server
    g_server = Process(target=run_global_server, args=(8020,))
    g_server.start()
    server_processes.append(g_server)

    for cluster_name, cluster_info in cluster_config['clusters'].items():
        # Start the cluster API server
        p_server = Process(target=run_cluster_server, args=(cluster_name, int(cluster_info['port'])))
        p_server.start()
        server_processes.append(p_server)

        # Start port-forward directly (non-blocking)
        service_port = 8080
        local_port = int(cluster_info['llama-service'])
        run_cmd_bg([
            "kubectl",
            "--kubeconfig", str(SRC_DIR / "cluster_api" / "auth" / f"k3d-devcluster-{cluster_name}.yaml"),
            "port-forward",
            "services/llama-service",
            f"{local_port}:{service_port}"
        ])

    # Wait for Uvicorn servers to finish
    for p in server_processes:
        p.join()


if __name__ == "__main__":
    start_all_servers()
