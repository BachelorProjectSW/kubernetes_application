import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "clusters.yaml"


def get_all_clusters_ip():
    """Return each clusters ip address."""
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)

    result = {}

    for name in data["clusters"]:
        cluster = data["clusters"][name]
        result[name] = cluster["ip"]

    return result
