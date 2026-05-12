import threading
from ...models.basemodels import Config, ClusterInformation
import requests


class ConfigStore:
    """Store for the current config.

    Thread-safe: get/set are protected by a lock so that the power scheduler
    thread and request handler threads never observe a partially-written config.
    """

    def __init__(self):
        """Initialize an empty, thread-safe configuration store.

        Returns:
            None: Creates internal state used by service threads.
        """
        self._config: Config | None = None
        self._lock = threading.Lock()

    def set(self, config: Config):
        """Replace the active test configuration.

        Args:
            config: Fully validated configuration to store as the current
                runtime configuration.

        Returns:
            None: Updates internal shared state under lock.
        """
        with self._lock:
            self._config = config

    def get(self) -> Config | None:
        """Get the currently active configuration.

        Returns:
            Config | None: The current configuration if one has been set,
            otherwise ``None``.
        """
        with self._lock:
            return self._config

    def get_clusters(self):
        """Get cluster definitions from the active configuration.

        Returns:
            list: Configured clusters, or an empty list if no configuration is
            active.
        """
        with self._lock:
            if self._config is None:
                return []
            return self._config.clusters

    def get_cluster_information(self):
        """Fetch runtime cluster information from each configured cluster API.

        The method snapshots cluster endpoints under lock and then performs
        network requests without holding the lock.

        Returns:
            list[ClusterInformation]: Parsed cluster information objects from
            all reachable cluster APIs.

        Raises:
            requests.RequestException: If a cluster API request fails.
            ValueError: If the response payload cannot be parsed into
                ``ClusterInformation``.
        """
        all_clusters = []

        with self._lock:
            if self._config is None:
                return all_clusters
            clusters = list(self._config.clusters)

        for cluster_cfg in clusters:
            url = f"http://{cluster_cfg.ip}:{cluster_cfg.port}/get_cluster_information"

            response = requests.get(url, timeout=180)
            response.raise_for_status()

            data = response.json()

            cluster_info = ClusterInformation(**data)

            all_clusters.append(cluster_info)

        return all_clusters

    def stop_power_scheduler(self):
        """Signal the active configuration to stop the power scheduler.

        Returns:
            None: Mutates the scheduler start flag when a config is present.
        """
        with self._lock:
            if self._config is None:
                return
            self._config.power_scheduler.start = False


config_store = ConfigStore()
