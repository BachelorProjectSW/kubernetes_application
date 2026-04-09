import math
import requests
import structlog
import asyncio
from ...models.basemodels import Config, ClusterInformation
from ...models.enum import WorkerStatus
from .scoring import score_cluster
from ..util.all_configuration import config_store
from ...custom_logging.util.log_reader import get_avg_latency, get_request_logs
from datetime import datetime, timezone


log = structlog.get_logger()


def get_current_active_nodes(clusters: list[ClusterInformation]):
    """Analise logs."""
    active_nodes_counter = 0
    for cluster in clusters:
        for worker_node in cluster.worker_nodes:
            status = worker_node.status
            if status == WorkerStatus.WORKING or status == WorkerStatus.IDLE:
                active_nodes_counter += 1
    log.info("get.current.active.nodes", active_nodes=active_nodes_counter)
    return active_nodes_counter


def get_current_rps(time_interval_s: int) -> float:
    """Return requests per second (RPS) in the last time_interval_s seconds.

    Args:
        time_interval_s: How far back to look, in seconds.

    Returns:
        Requests per second as a float. Returns 0.0 if no requests.

    """
    now = datetime.now(timezone.utc)
    count = 0
    all_request = get_request_logs()
    for request_log in all_request:
        age_s = (now - request_log.timestamp).total_seconds()
        if age_s <= time_interval_s:
            count += 1

    return round(count / time_interval_s, 2) if time_interval_s > 0 else 0.0


def estimate_nodes_to_add(
    avg_latency_per_node_ms: float,
    max_latency_ms: float,
    current_active_nodes: int,
    current_rps: float,
) -> int:
    """Estimate how many more worker nodes are needed.

    to keep latency under max_latency_s.
    """
    # how many nodes needed in total
    required_nodes = math.ceil((avg_latency_per_node_ms * current_rps) / max_latency_ms)
    log.debug("required nodes", number=required_nodes)

    # how many more to add
    nodes_to_add = max(0, required_nodes - current_active_nodes)

    log.info("estimated.nodes.to.add", number_of_nodes=nodes_to_add)
    return nodes_to_add


def turn_nodes_on(config: Config, clusters: list[ClusterInformation]):
    """Turn nodes on."""
    # Sort clusters by score (highest first)
    sorted_clusters = sorted(
        clusters,
        key=lambda cluster: score_cluster(
            cluster.cluster_config.renewable_output_w,
            cluster.cluster_config.cluster_load_w,
            cluster.cluster_config.grid_carbon_intensity,
            cluster.cluster_config.grid_electricity_price,
            config.weights.gco2,
            config.weights.cost,
            config.energy,
        ),
        reverse=True,  # highest first
    )

    avg_latency_ms = get_avg_latency(config.power_scheduler.timeout_s)
    max_latency_ms = config.latency.max_ms
    current_active_nodes = get_current_active_nodes(clusters)
    current_rps = get_current_rps()

    nodes_to_add = estimate_nodes_to_add(
        avg_latency_ms,
        max_latency_ms,
        current_active_nodes,
        current_rps
    )
    for cluster in sorted_clusters:
        if nodes_to_add <= 0:
            break
        powered_off_nodes = 0
        for worker_node in cluster.worker_nodes:
            if worker_node.status == WorkerStatus.OFF:
                powered_off_nodes += 1

        log.debug(
            "cluster.capacity",
            cluster_ip=cluster.cluster_config.ip,
            cluster_port=cluster.cluster_config.port,
            powered_off_nodes=powered_off_nodes,
        )

        amount = min(nodes_to_add, powered_off_nodes)
        if amount <= 0:
            continue

        try:
            url = f"http://{cluster.cluster_config.ip}:{cluster.cluster_config.port}/turn_on_nodes/"
            response = requests.post(url, params={"number_of_nodes": amount}, timeout=10)
            turned_on = response.json().get("turned_on", amount)
            nodes_to_add -= turned_on
        except Exception as e:
            log.error("Power.On", error=e)


def turn_off_idle_nodes(config: Config):
    """Turn nodes off."""
    for cluster in config.clusters:
        try:
            url = f"http://{cluster.ip}:{cluster:port}/turn_off_idle_nodes/"
            idle_time = config.power_scheduler.idle_time_for_turn_off_s
            response = requests.post(url, params={"idle_time": idle_time}, timeout=20)
            response.raise_for_status()
        except Exception as e:
            log.error("Power.Off", error=e)


async def power_scheduler_loop():
    """Check every x seconds whether more working nodes should be turn on or off."""
    log.info("Global Power Scheduler Running")
    config = config_store.get()
    timeout = config.power_scheduler.timeout_s
    while config.power_scheduler.start:
        log.info("Global Power Scheduler Running Again")
        await asyncio.sleep(timeout)
        all_clusters = config_store.get_cluster_information()
        turn_nodes_on(config, all_clusters)
        turn_off_idle_nodes(config)
