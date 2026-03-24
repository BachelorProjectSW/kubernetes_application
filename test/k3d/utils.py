import subprocess
import yaml
import threading

CONFIG_PATH = "test/k3d/cluster_configs/config_clusters.yaml"

def run_cmd_bg(cmd):
    """
    Run a command in the background (non-blocking) and print stdout/stderr in real time.
    Designed for long-running commands like kubectl port-forward.
    """
    print(f"Running (background): {cmd}")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True  # decode output as string
    )

    # Print stdout asynchronously
    def stream_output(stream):
        for line in iter(stream.readline, ''):
            print(line, end='')

    threading.Thread(target=stream_output, args=(process.stdout,), daemon=True).start()
    threading.Thread(target=stream_output, args=(process.stderr,), daemon=True).start()

    return process  # Optional: keep a reference to terminate later if needed


def run_cmd(cmd):
    """Run bash command."""
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True)


def get_clusters():
    """Return cluster names and ip endpoint."""
    with open(CONFIG_PATH, "r") as f:
        data = yaml.safe_load(f)

    clusters = []

    for entry in data["clusters"]:
        cluster = {
            "name": entry["name"],
            "port": entry["port"],
            "llama-service": entry["llama-service"]
        }
        clusters.append(cluster)

    return clusters

def get_cluster_names():
    """Return all cluster names."""
    clusters = get_clusters()
    names = []
    for cluster in clusters:
        names.append(cluster["name"])
    return names

