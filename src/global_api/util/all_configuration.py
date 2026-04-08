from ...models.basemodels import Config
from datetime import datetime

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


config_store = ConfigStore()
