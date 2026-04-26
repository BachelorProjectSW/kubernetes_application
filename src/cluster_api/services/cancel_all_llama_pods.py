from http.client import HTTPException
import threading

import structlog

from .power_scheduler import run_cmd
from ...models.test_state import test_state

log = structlog.get_logger()


def cancel_all_llama_pods() -> dict:
    """Delete all llama pods and return when kubectl delete has completed."""

    try:
        stdout = run_cmd(
            "sudo kubectl delete pod -l app=llama-server --grace-period=0 --force"
        )

        log.info("cluster.llama_pods_deleted", stdout=stdout.strip())

        return {
            "message": "Llama pods deleted",
            "stdout": stdout,
        }

    except Exception as e:
        log.exception("cluster.llama_pods_delete_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete llama pods: {e}",
        ) from e