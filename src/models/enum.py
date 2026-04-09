from enum import Enum


class WorkerStatus(str, Enum):
    """Workernodes status."""

    OFF = "off"
    TURNING_ON = "turning_on"
    TURNING_OFF = "turning_off"
    WORKING = "working"
    IDLE = "idle"