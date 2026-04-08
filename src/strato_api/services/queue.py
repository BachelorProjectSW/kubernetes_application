from ...models.basemodels import Config
from typing import List


class ConfigQueue:
    """Manage a queue of Config objects."""

    def __init__(self):
        """Init queue."""
        self.queue: List[Config] = []

    def get_queue(self) -> List[Config]:
        """Return the current queue."""
        return self.queue


config_manager = ConfigQueue()
