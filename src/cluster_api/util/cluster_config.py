from ...models.basemodels import ClusterInformation


class ConfigStore:
    """Store for the current cluster config."""
    
    def __init__(self):
        """init config to none."""
        self.config: ClusterInformation | None = None

    def set(self, config: ClusterInformation):
        """Set the current config."""
        self.config = config

    def get(self):
        """Get the current config."""
        return self.config
    

config_store = ConfigStore()