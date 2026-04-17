import threading
from ...models.basemodels import Config, ClusterInformation
import requests


class ConfigStore:
    """Store for the current config.

    Thread-safe: get/set are protected by a lock so that the power scheduler
    thread and request handler threads never observe a partially-written config.
    """

    def __init__(self):
        """Init config to none."""
        self._config: Config | None = None
        self._lock = threading.Lock()

    def set(self, config: Config):
        """Set the current config."""
        with self._lock:
            self._config = config

    def get(self) -> Config | None:
        """Get the current config."""
        with self._lock:
            return self._config

    def get_clusters(self):
        """Return clusters."""
        with self._lock:
            return self._config.clusters

    def get_cluster_information(self):
        """Return all cluster informations."""
        all_clusters = []

        with self._lock:
            clusters = list(self._config.clusters)

        for cluster_cfg in clusters:
            url = f"http://{cluster_cfg.ip}:{cluster_cfg.port}/get_cluster_information"

            response = requests.get(url, timeout=20)
            response.raise_for_status()

            data = response.json()

            cluster_info = ClusterInformation(**data)

            all_clusters.append(cluster_info)

        return all_clusters

    def stop_power_scheduler(self):
        """Stop power scheduler."""
        with self._lock:
            self._config.power_scheduler.start = False


config_store = ConfigStore()
