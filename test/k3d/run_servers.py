import os
import sys
from pathlib import Path
from multiprocessing import Process
import uvicorn
from utils import get_clusters, run_cmd

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"

# Ensure child processes can import the top-level src package regardless of launch cwd.
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def run_server(cluster_name, port):
    kubeconfig = SRC_DIR / "cluster_api" / "auth" / f"k3d-devcluster-{cluster_name}.yaml"
    os.environ["KUBECONFIG"] = str(kubeconfig)
    uvicorn.run("src.cluster_api.cluster_api_app:app", host="0.0.0.0", port=port)

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
    run_cmd(cmd)

def start_all_servers():
    clusters = get_clusters()
    processes = []

    for cluster in clusters:
        # Start the cluster API server
        p_server = Process(target=run_server, args=(cluster["name"], int(cluster["port"])))
        p_server.start()
        processes.append(p_server)

        # Start port-forwarding in a separate process
        service_port = 8080 
        p_pf = Process(target=run_port_forward, args=(cluster["name"], int(cluster["llama-service"]), service_port))
        p_pf.start()
        processes.append(p_pf)

    # Wait for all processes to finish (this will block)
    for p in processes:
        p.join()

if __name__ == "__main__":
    start_all_servers()