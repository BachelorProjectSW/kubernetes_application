import os
from multiprocessing import Process
import uvicorn
from utils import get_clusters

def run_server(cluster_name, port):
    kubeconfig = f"src/cluster_api/auth/k3d-devcluster-{cluster_name}.yaml"
    os.environ["KUBECONFIG"] = kubeconfig
    uvicorn.run("src.cluster_api.main:app", host="0.0.0.0", port=port)

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
