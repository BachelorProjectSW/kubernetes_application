import threading

#TODO change to enum

class TestState:
    def __init__(self):
        self._lock = threading.Lock()
        self._status = "idle"   # idle | running | stopping

    def start(self):
        with self._lock:
            self._status = "running"

    def mark_stopping(self):
        with self._lock:
            if self._status == "running":
                self._status = "stopping"

    def reset(self):
        with self._lock:
            self._status = "idle"

    def is_running(self) -> bool:
        with self._lock:
            return self._status == "running"

    def is_stopping(self) -> bool:
        with self._lock:
            return self._status == "stopping"

    def get_status(self) -> str:
        with self._lock:
            return self._status

test_state = TestState()
