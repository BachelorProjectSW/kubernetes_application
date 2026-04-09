from ...models.basemodels import Config, ClusterInformation
import requests


class ConfigStore:
    """Store for the current config."""

    def __init__(self):
        """Init config to none."""
        self.config: Config | None = None

    def set(self, config: Config):
        """Set the current config."""
        self.config = config

    def get(self):
        """Get the current config."""
        return self.config

    def get_clusters(self):
        """Return clusters."""
        return self.config.clusters

    def get_cluster_information(self):
        """Return all cluster informations."""
        all_clusters = []

        for cluster_cfg in self.config.clusters:
            url = f"http://{cluster_cfg.ip}:{cluster_cfg.port}/get_cluster_information"

            response = requests.get(url, timeout=20)
            response.raise_for_status()

            data = response.json()

            cluster_info = ClusterInformation(**data)

            all_clusters.append(cluster_info)

        return all_clusters

    def stop_power_scheduler(self):
        """Stop power scheduler."""
        self.config.power_scheduler.start = False


config_store = ConfigStore()
