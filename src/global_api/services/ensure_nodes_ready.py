import requests
import structlog
import time

log = structlog.get_logger()


def ensure_nodes_ready(cluster, timeout_s, poll_interval_s: int = 5):
    """Turn on all nodes in cluster and wait until they are ready.
    """
    base = f"http://{cluster.ip}:{cluster.port}"

    # Step 1: Get total node count
    try:
        info = requests.get(f"{base}/get_cluster_information", timeout=10).json()
    except Exception as e:
        log.warning("ensure_nodes_ready.info_failed", cluster=cluster.name, error=str(e))
        return

    nodes = info.get("worker_nodes", [])
    total = len(nodes)
    log.info("ensure_nodes_ready.turning_on", cluster=cluster.name, total=total)

    # Step 2: Turn on all nodes (even if already on)
    try:
        requests.post(
            f"{base}/turn_on_nodes/",
            params={"number_of_nodes": total},
            timeout=30,
        )
    except Exception as e:
        log.warning("ensure_nodes_ready.turn_on_failed", cluster=cluster.name, error=str(e))

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            response = requests.get(f"{base}/get_cluster_working_nodes", timeout=10)
            response.raise_for_status()
            worker_nodes = response.json()

            ready = [n for n in worker_nodes if n["status"] == "idle" and n["max_slots"] > 0]
            log.info(
                "ensure_nodes_ready.polling",
                cluster=cluster.name,
                ready=len(ready),
                total=total,
            )

            if len(ready) >= total:
                log.info("ensure_nodes_ready.all_ready", cluster=cluster.name)
                return

        except Exception as e:
            log.warning("ensure_nodes_ready.poll_failed", cluster=cluster.name, error=str(e))

        time.sleep(poll_interval_s)

    log.warning("ensure_nodes_ready.timeout", cluster=cluster.name, timeout_s=timeout_s)