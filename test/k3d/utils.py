import subprocess
import yaml

CONFIG_PATH = "test/k3d/cluster_configs/config_clusters.yaml"


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
            "port": entry["port"]
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

