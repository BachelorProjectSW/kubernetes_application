import subprocess
import threading
from pathlib import Path
import yaml

def get_test_cluster_config():
    test_config_path = Path(__file__) / "cluster_configs" / "test_clusters.yaml"

    with open(test_config_path) as f:
        return yaml.safe_load(f)

def run_cmd_bg(cmd):
    """Run a command in the background (non-blocking) and print stdout/stderr in real time.

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
