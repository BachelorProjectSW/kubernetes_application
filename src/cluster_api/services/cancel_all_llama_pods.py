import structlog

from .power_scheduler import run_cmd

log = structlog.get_logger()


def cancel_all_llama_pods():
    """
    Immediately remove every running Llama pod so they restart cleanly.

    Simple explanation:
    - This tells Kubernetes to delete all pods that are part of the Llama service.
    - The cluster is configured with a DaemonSet for the Llama server, so Kubernetes
      will automatically recreate the pods after they are deleted. Use this when
      you need a clean restart of the model processes on every node.

    Parameters:
        None

    Returns:
        None. The function logs success or failure and does not return a value.

    """
    try:
        stdout = run_cmd("sudo kubectl delete pods -l app=llama-server")
        log.info("cluster.llama_pods_deleted", stdout=stdout.strip())
    except Exception as e:
        log.error("cluster.llama_pods_delete_failed", error=str(e))
