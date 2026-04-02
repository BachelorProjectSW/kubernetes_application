import os
import sys
from pathlib import Path
from multiprocessing import Process
import uvicorn
from utils import get_cluster_config

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"


# Ensure child processes can import the top-level src package regardless of launch cwd.
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def run_global_server(port):
    """Run Global server."""
    uvicorn.run("src.global_api.app:app", host="0.0.0.0", port=port)


def run_strato_server(port):
    """Run Strato server."""
    uvicorn.run("src.strato_api.app:app", host="0.0.0.0", port=port)


def run_cluster_server(cluster_name, port):
    """Run cluster server."""
    kubeconfig = SRC_DIR / "cluster_api" / "auth" / f"k3d-devcluster-{cluster_name}.yaml"
    os.environ["KUBECONFIG"] = str(kubeconfig)
    uvicorn.run("src.cluster_api.app:app", host="0.0.0.0", port=port)


def start_all_servers():
    """Start strato, global scheduler, all cluster control planes, and port-forward the llama-services."""
    cluster_config = get_cluster_config()
    server_processes = []

    # Start the global scheduler API server
    g_server = Process(target=run_global_server, args=(8020,))
    g_server.start()
    server_processes.append(g_server)

    # Start the Strato API server
    g_server = Process(target=run_global_server, args=(8090,))
    g_server.start()
    server_processes.append(g_server)

    for cluster in cluster_config:
        # Start the cluster API server
        p_server = Process(target=run_cluster_server, args=(cluster.name, int(cluster.port)))
        p_server.start()
        server_processes.append(p_server)


    # Wait for Uvicorn servers to finish
    for p in server_processes:
        p.join()


if __name__ == "__main__":
    start_all_servers()
