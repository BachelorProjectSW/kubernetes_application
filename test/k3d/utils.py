import shlex
import subprocess
from test.k3d.cluster_configs.test_config import get_test_config


def get_config():
    """Return config."""
    return get_test_config()


def get_cluster_config():
    """Return cluster config."""
    config = get_test_config()
    return config.clusters


def get_cluster_names():
    """Return a list with cluster names."""
    clusters = get_cluster_config()
    names = []
    for cluster in clusters:
        name = cluster.name
        names.append(name)
    return names


def run_cmd(cmd):
    """Run bash command."""
    if isinstance(cmd, list):
        cmd = shlex.join(cmd)

    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True)


def run_cmd_bg(cmd):
    """Run a command in the background (non-blocking) and print stdout/stderr in real time.

    Designed for long-running commands like kubectl port-forward.
    """
    print(f"Running (background): {cmd}")
    subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True  # decode output as string
    )
