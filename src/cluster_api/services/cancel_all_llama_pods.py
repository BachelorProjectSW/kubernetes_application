import subprocess
import structlog

log = structlog.get_logger()

def cancel_all_llama_pods():
    """Delete all llama pods — DaemonSet restarts them automatically."""
    try:
        result = subprocess.run(
            ["sudo", "kubectl", "delete", "pods", "-l", "app=llama-server"],
                capture_output=True,
                text=True,
                timeout=60
        )
        log.info("cluster.llama_pods_deleted", stdout=result.stdout.strip())
    except Exception as e:
        log.error("cluster.llama_pods_delete_failed", error=str(e))