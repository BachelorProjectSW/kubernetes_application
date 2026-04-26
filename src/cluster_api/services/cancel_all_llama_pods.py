import threading

import structlog

from .power_scheduler import run_cmd

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
    threading.Thread(
        target=_cancel_all_llama_pods_background,
        daemon=True,
        name="cancel-all-llama-pods",
    ).start()
    return {"message": "Llama pod restart requested"}