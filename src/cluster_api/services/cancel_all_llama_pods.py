import structlog

from cluster_api.services.power_scheduler import run_cmd

log = structlog.get_logger()


def cancel_all_llama_pods():
    """Delete all llama pods, DaemonSet restarts them automatically."""
    try:
        stdout = run_cmd("sudo kubectl delete pods -l app=llama-server")
        log.info("cluster.llama_pods_deleted", stdout=stdout.strip())
    except Exception as e:
        log.error("cluster.llama_pods_delete_failed", error=str(e))
