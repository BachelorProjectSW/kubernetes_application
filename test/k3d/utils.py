import subprocess
from src.models.basemodels import *
from .cluster_configs.test_config import get_test_config


def get_cluster_config():
    config = get_test_config()
    return config.clusters


def get_cluster_names():
    clusters = get_cluster_config()
    print(clusters)
    names = []
    for cluster in clusters:
        name = cluster.name
        print(name)
        names.append(name)
    return names

def run_cmd(cmd):
    """Run bash command."""
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True)
