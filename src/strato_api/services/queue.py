from ...models.basemodels import Config
from typing import List


class ConfigQueue:
    """Manage a queue of Config objects."""

    def __init__(self):
        """Init queue."""
        self.queue: List[Config] = []

    # --- Queue management ---
    def add_to_queue(self, config: Config):
        """Add a new config to the queue."""
        self.queue.append(config)
        return self.queue

    def remove_from_queue(self, config_id: str):
        """Remove a config from the queue by ID. Returns queue."""
        for i, config in enumerate(self.queue):
            if config.id == config_id:
                self.queue.pop(i)
                break
        return self.queue

    def get_queue(self) -> List[Config]:
        """Return the current queue."""
        return self.queue


config_manager = ConfigQueue()
