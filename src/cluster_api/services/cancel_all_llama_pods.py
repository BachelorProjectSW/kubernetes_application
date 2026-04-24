import threading

import structlog

from .power_scheduler import run_cmd
from ..services.test_state import test_state

log = structlog.get_logger()

def _cancel_all_llama_pods_background():
    """Restart llama pods in the background."""
    try:
        stdout = run_cmd(
            "sudo kubectl delete pod -l app=llama-server --grace-period=0 --force")
        log.info("cluster.llama_pods_deleted", stdout=stdout.strip())
    except Exception as e:
        log.exception("cluster.llama_pods_delete_failed", error=str(e))


def cancel_all_llama_pods():
    """Request llama pod restart and return immediately."""
    if test_state.is_stopping():
        return {"message": "Cancel already in progress"}
    threading.Thread(
        target=_cancel_all_llama_pods_background,
        daemon=True,
        name="cancel-all-llama-pods",
    ).start()

    return {"message": "Llama pod restart requested"}