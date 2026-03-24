import os
import sys
from pathlib import Path
from multiprocessing import Process
import uvicorn
from utils import get_clusters

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"

# Ensure child processes can import the top-level src package regardless of launch cwd.
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def run_server(cluster_name, port):
    kubeconfig = SRC_DIR / "cluster_api" / "auth" / f"k3d-devcluster-{cluster_name}.yaml"
    os.environ["KUBECONFIG"] = str(kubeconfig)
    uvicorn.run("src.cluster_api.cluster_api_app:app", host="0.0.0.0", port=port)

def start_all_servers():
    clusters = get_clusters()
    processes = []
    for cluster in clusters:
        p = Process(target=run_server, args=(cluster["name"], cluster["port"]))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

if __name__ == "__main__":
    start_all_servers()

