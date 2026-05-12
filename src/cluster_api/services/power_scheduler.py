import paramiko
import structlog
from concurrent.futures import ThreadPoolExecutor
from ...models.basemodels import WorkerNode
from ..util.cluster_config import config_store
from ..util.client_setup import get_api_client
from ...models.enum import WorkerStatus
from ...custom_logging.util.log_reader import get_worker_nodes_logs
from datetime import datetime, timezone
import subprocess
import time
from ...custom_logging.logger import log_node_status_snapshot
import requests

log = structlog.get_logger()


def run_cmd(cmd):
    """Run bash command."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def turn_on_node(worker_node: WorkerNode, cluster_name: str):
    """Turn on the node via GPIO."""
    try:
        gpio = worker_node.gpio
        log.debug(
            "cluster_api.power.turn_on_gpio_pulse_started",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            gpio=gpio,
        )
        run_cmd(f"sudo gpioset gpiochip4 {gpio}=1")
        time.sleep(0.5)
        run_cmd(f"sudo gpioset gpiochip4 {gpio}=0")
        log.debug(
            "cluster_api.power.turn_on_gpio_pulse_completed",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            gpio=gpio,
        )
        worker_node.status = WorkerStatus.TURNING_ON
        log_node_status_snapshot(cluster_name, worker_node)
        return True
    except Exception as e:
        log.warning(
            "cluster_api.power.turn_on_failed",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            error=str(e),
        )
        return False


def turn_off_node(worker_node: WorkerNode, cluster_name: str):
    """Turn of node with SSH."""
    try:
        log.info("cluster_api.power.turning_off_node", cluster=cluster_name, node=worker_node)
        worker_node.status = WorkerStatus.TURNING_OFF
        log_node_status_snapshot(cluster_name, worker_node)
        time.sleep(10)

        if worker_node.inflight_requests > 0:
            worker_node.status = WorkerStatus.IDLE
            log_node_status_snapshot(cluster_name, worker_node)
            log.warning(
                "cluster_api.power.turn_off_aborted_inflight_requests",
                cluster_name=cluster_name,
                worker_node=worker_node.name,
                inflight_requests=worker_node.inflight_requests,
            )
            return False

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(
            hostname=worker_node.ip,
            username=worker_node.name,
            password=worker_node.name
        )

        # -S makes sudo read password from stdin
        command = "sudo -S shutdown now"

        stdin, stdout, stderr = client.exec_command(command)

        # send password to sudo
        stdin.write(worker_node.name + "\n")
        stdin.flush()

        # read output
        out = stdout.read().decode()
        err = stderr.read().decode()

        log.debug(
            "cluster_api.power.turn_off_shutdown_stdout",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            stdout=out,
        )
        log.debug(
            "cluster_api.power.turn_off_shutdown_stderr",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            stderr=err,
        )

        client.close()
        time.sleep(20)
        worker_node.status = WorkerStatus.OFF
        log_node_status_snapshot(cluster_name, worker_node)
        return True
    except Exception as e:
        worker_node.status = WorkerStatus.IDLE
        log_node_status_snapshot(cluster_name, worker_node)
        log.warning(
            "cluster_api.power.turn_off_failed",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            error=str(e),
        )
        return False


def check_if_llama_pod_is_ready(
    worker_node: WorkerNode,
    api_client,
    cluster_name: str,
    namespace: str = "default"
    ) -> bool:
    """Return True when a llama pod on this node is Running and Ready."""
    try:
        pods = api_client.list_namespaced_pod(
            namespace=namespace,
            field_selector=f"spec.nodeName={worker_node.name}",
            label_selector="app=llama-server",
        ).items

        for pod in pods:
            if getattr(pod.status, "phase", None) != "Running":
                continue

            conditions = getattr(pod.status, "conditions", None) or []
            pod_ready = any(c.type == "Ready" and c.status == "True" for c in conditions)

            container_statuses = getattr(pod.status, "container_statuses", None) or []
            containers_ready = bool(container_statuses) and all(cs.ready for cs in container_statuses)

            if pod_ready and containers_ready:
                return True

        return False

    except Exception as e:
        log.warning(
            "cluster_api.power.pod_readiness_check_failed",
            cluster_name=cluster_name,
            worker_node=worker_node.name,
            error=str(e),
        )
        return False

def refresh_worker_capacity(worker_node: WorkerNode, cluster_config) -> bool:
    """Refresh max_slots for a single worker from its llama /props endpoint."""
    try:
        if cluster_config.cluster_config.k3d:
            url = f"http://localhost:{worker_node.forwarded_port}/props"
        else:
            url = f"http://{worker_node.ip}:{cluster_config.cluster_config.llama_hostport}/props"

        log.debug(
            "cluster_api.power.worker_capacity_refresh_started",
            cluster_name=cluster_config.cluster_config.name,
            worker_node=worker_node.name,
            url=url,
        )

        response = requests.get(url, timeout=120)
        response.raise_for_status()
        props = response.json()

        worker_node.max_slots = props.get("total_slots", 0)

        if worker_node.max_slots > 0:
            worker_node.status = WorkerStatus.IDLE
            log_node_status_snapshot(cluster_config.cluster_config.name, worker_node)
            return True

        log.warning(
            "cluster_api.power.worker_capacity_refresh_zero_slots",
            cluster_name=cluster_config.cluster_config.name,
            worker_node=worker_node.name,
            props=props,
        )
        return False

    except Exception as e:
        log.warning(
            "cluster_api.power.worker_capacity_refresh_failed",
            cluster_name=cluster_config.cluster_config.name,
            worker_node=worker_node.name,
            error=str(e),
        )
        return False


def wait_for_nodes_to_be_ready(
        worker_nodes: list[WorkerNode],
        cluster_name: str,
        timeout_s: int = 300,
        poll_interval_s: int = 2
        ) -> bool:
    """Wait until each selected node has a Running+Ready llama pod and valid capacity."""
    deadline = time.time() + timeout_s
    api_client = get_api_client()
    cluster_config = config_store.get()

    while time.time() < deadline:
        ready_nodes = []

        for node in worker_nodes:
            pod_ready = check_if_llama_pod_is_ready(node, api_client, cluster_name)

            if not pod_ready:
                continue

            capacity_ready = refresh_worker_capacity(node, cluster_config)

            if capacity_ready:
                ready_nodes.append(node)
            else:
                # Keep it as turning_on while /props is not ready yet
                node.status = WorkerStatus.TURNING_ON
                log_node_status_snapshot(cluster_name, node)

        if len(ready_nodes) == len(worker_nodes):
            return True

        time.sleep(poll_interval_s)

    for node in worker_nodes:
        if node.status not in {WorkerStatus.IDLE, WorkerStatus.WORKING}:
            node.status = WorkerStatus.OFF
            node.max_slots = 0
            log_node_status_snapshot(cluster_name, node)
            log.warning("cluster_api.power.pod_not_ready", cluster=cluster_name, node=node)

    return False

def change_node_status(number_of_nodes: int, status: str):
    """Change status of up to number_of_nodes in the cluster.

    status: 'on' or 'off'.
    """
    cluster_config = config_store.get()
    cluster_name = cluster_config.cluster_config.name
    nodes = cluster_config.worker_nodes
    if status == "on":
        nodes_to_change = select_nodes_to_turn_on(number_of_nodes, nodes)
        with ThreadPoolExecutor(max_workers=max(1, len(nodes_to_change))) as executor:
            futures = [executor.submit(turn_on_node, node, cluster_name) for node in nodes_to_change]
            for future in futures:
                future.result()

        ready = wait_for_nodes_to_be_ready(nodes_to_change, cluster_name)

        if not ready:
            log.warning(
                "cluster_api.power.turn_on_nodes_not_all_ready",
                cluster_name=cluster_name,
                nodes=[node.name for node in nodes_to_change],
            )

    elif status == "off":
        nodes_to_change = select_nodes_to_turn_off(number_of_nodes, nodes)
        for node in nodes_to_change:
            turn_off_node(node, cluster_config.cluster_config.name)
    else:
        raise ValueError("status must be 'on' or 'off'")

    return {
        "requested": number_of_nodes,
        "status": status,
        "node_changed": len(nodes_to_change),
        "nodes": [node.name for node in nodes_to_change],
    }


def select_nodes_to_turn_on(number_of_nodes: int, worker_nodes: list[WorkerNode]) -> list[WorkerNode]:
    """Select inactive nodes to turn on."""
    nodes_to_turn_on = []
    for node in worker_nodes:
        if len(nodes_to_turn_on) >= number_of_nodes:
            break
        if node.status == WorkerStatus.OFF:
            nodes_to_turn_on.append(node)
            continue
        
        if node.status == WorkerStatus.TURNING_ON and node.max_slots == 0:
            nodes_to_turn_on.append(node)
            continue
    return nodes_to_turn_on


def select_nodes_to_turn_off(number_of_nodes: int, worker_nodes: list[WorkerNode]) -> list[WorkerNode]:
    """Select active nodes to turn off, this is only used for manually turn off x nodes."""
    nodes_to_turn_off = []
    for node in worker_nodes:
        if len(nodes_to_turn_off) >= number_of_nodes:
            break
        if node.status == WorkerStatus.IDLE:
            nodes_to_turn_off.append(node)
    return nodes_to_turn_off


def get_idle_time(node_name: str, cluster_name: str) -> float:
    """Return the idle time in seconds for a given node in a cluster.

    Checks the most recent NodeStatusLog entry for this node. If it shows status==IDLE,
    returns the seconds since that transition. Otherwise returns 0 (node not currently idle).

    Args:
        node_name: Name of the node to check.
        cluster_name: Name of the cluster the node belongs to.

    Returns:
        Time in seconds since the node transitioned to IDLE.
        Returns 0 if the most recent status is not IDLE.

    """
    now = datetime.now(timezone.utc)

    try:
        config = config_store.get()
        config_id = config.config_id
        entry = get_worker_nodes_logs(config_id, cluster_name, node_name)
    except Exception as e:
        log.debug("cluster_api.power.get_worker_nodes_logs", error=str(e))
        return 0

    if entry is None:
        # No log entry found for this node; conservatively return 0 (don't turn off)
        return 0

    log.debug("cluster_api.power.entry_debug", entry=entry)
    log.debug("cluster_api.power.latest_node_change", status=entry.status)
    if str(entry.status).lower() == WorkerStatus.IDLE.value:
        log.debug("cluster_api.power.latest_node_change", changed=True)
        return (now - entry.timestamp).total_seconds()

    log.debug("cluster_api.power.latest_node_change", changed=False)
    return 0


def turn_off_idle_nodes(idle_time: int, stay_one: bool = False):
    """Turn off all nodes that have been idle for longer than `idle_time` seconds.

    Args:
        idle_time: Number of seconds a node must be idle before being turned off.
        stay_one: If its the best cluster after running scoring algorithm then at least stay one up.

    """
    config = config_store.get()
    cluster_name = config.cluster_config.name
    config_id = config.config_id
    if not config_id:
        log.warning(
            "cluster_api.power.turn_off_idle_skipped_missing_config_id",
            cluster_name=cluster_name,
            worker_node=None,
        )
        return

    nodes = config.worker_nodes

    if stay_one:
        active_or_idle_nodes = 0
        for node in nodes:
            if node.status in {WorkerStatus.WORKING, WorkerStatus.IDLE}:
                active_or_idle_nodes += 1
        if active_or_idle_nodes <= 1:
            log.debug(
                "cluster_api.power.turn_off_idle_stay_one_protected",
                cluster_name=cluster_name,
                active_or_idle_nodes=active_or_idle_nodes,
            )
            return {
                "requested": 0,
                "status": "off",
                "node_changed": 0,
                "nodes": [],
            }

    for node in nodes:
        # Only true idle nodes are eligible for automatic power-off.
        if node.status != WorkerStatus.IDLE:
            log.debug(
                "cluster_api.power.turn_off_idle_skipped_status",
                cluster_name=cluster_name,
                worker_node=node.name,
                status=node.status,
            )
            continue

        # Never power off a node while requests are still inflight.
        if node.inflight_requests > 0:
            log.debug(
                "cluster_api.power.turn_off_idle_skipped_inflight",
                cluster_name=cluster_name,
                worker_node=node.name,
                inflight_requests=node.inflight_requests,
            )
            continue

        last_request = get_idle_time(node.name, cluster_name)
        log.debug("cluster_api.power.last_request", last_request=last_request)
        if last_request > idle_time:
            log.info(
                "cluster_api.power.turn_off_idle_node_selected",
                cluster_name=cluster_name,
                worker_node=node.name,
                last_request_age_s=last_request,
                idle_time_s=idle_time,
            )
            turn_off_node(node, cluster_name)
        else:
            log.debug(
                "cluster_api.power.turn_off_idle_skipped_recent_request",
                cluster_name=cluster_name,
                worker_node=node.name,
                last_request_age_s=last_request,
                idle_time_s=idle_time,
            )
