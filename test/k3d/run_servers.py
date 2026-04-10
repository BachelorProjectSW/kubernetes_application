import os
import sys
from pathlib import Path
from multiprocessing import Process
import json
import uvicorn

from src.models.basemodels import ClusterInformation
from .utils import get_cluster_config, get_test_config, run_cmd, run_cmd_bg
from src.cluster_api.util.cluster_config import config_store

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
    full_config = get_test_config()
    cluster_config = next(
        cluster for cluster in full_config.clusters
        if cluster.name == cluster_name
    )

    cluster_information = ClusterInformation(
        cluster_config=cluster_config,
        question_config=full_config.question,
        worker_nodes=[],
    )

    config_store.set(cluster_information)
    config_store.build_worker_nodes()
    uvicorn.run("src.cluster_api.app:app", host="0.0.0.0", port=port)


def get_llama_pods(cluster_name: str) -> list[dict]:
    """Return llama pods with pod name and node name."""
    kubeconfig = SRC_DIR / "cluster_api" / "auth" / f"k3d-devcluster-{cluster_name}.yaml"

    output = run_cmd([
        "kubectl",
        "--kubeconfig", str(kubeconfig),
        "get", "pods",
        "-l", "app=llama-server",
        "-o", "json",
    ])

    data = json.loads(output)
    pods = []

    for item in data["items"]:
        pod_name = item["metadata"]["name"]
        node_name = item["spec"].get("nodeName")
        phase = item["status"].get("phase")

        if phase == "Running" and node_name:
            pods.append({
                "pod_name": pod_name,
                "node_name": node_name,
            })

    pods.sort(key=lambda pod: pod["node_name"])  # Sort by name
    return pods


def start_pod_forwards(cluster_name: str, base_local_port: int):
    """Start one port-forward per llama pod."""
    kubeconfig = SRC_DIR / "cluster_api" / "auth" / f"k3d-devcluster-{cluster_name}.yaml"
    pods = get_llama_pods(cluster_name)

    for index, pod in enumerate(pods):
        local_port = base_local_port + index

        run_cmd_bg([
            "kubectl",
            "--kubeconfig", str(kubeconfig),
            "port-forward",
            f"pod/{pod['pod_name']}",
            f"{local_port}:8080",
        ])


def start_all_servers():
    """Start strato, global scheduler, all cluster control planes, and port-forward the llama-services."""
    configs = get_test_config()
    cluster_config = get_cluster_config()
    server_processes = []

    # Start the global scheduler API server
    g_server = Process(target=run_global_server, args=(int(configs.global_scheduler.port),))
    g_server.start()
    server_processes.append(g_server)

    # Start the Strato API server
    g_server = Process(target=run_strato_server, args=(int(configs.strato.port),))
    g_server.start()
    server_processes.append(g_server)

    for cluster in cluster_config:
        # Start the cluster API server
        p_server = Process(target=run_cluster_server, args=(cluster.name, int(cluster.port)))
        p_server.start()
        server_processes.append(p_server)

        # Start port-forward directly (non-blocking)
        start_pod_forwards(cluster.name, base_local_port=int(cluster.llama_service_port))

    # Wait for Uvicorn servers to finish
    for p in server_processes:
        p.join()


if __name__ == "__main__":
    start_all_servers()
