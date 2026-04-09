from enum import Enum


class WorkerStatus(str, Enum):
    """Workernodes status.

    Values:
        OFF: Node is powered off.
        TURNING_ON: Node is in the process of starting up.
        TURNING_OFF: Node is in the process of shutting down.
        WORKING: Node is actively handling workload.
        IDLE: Node is running but not currently processing tasks.
    """

    OFF = "off"
    TURNING_ON = "turning_on"
    TURNING_OFF = "turning_off"
    WORKING = "working"
    IDLE = "idle"
