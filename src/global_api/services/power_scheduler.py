import math
import requests
import structlog
import asyncio
from ...models.basemodels import Config, ClusterInformation, ClusterRuntimeData
from ...models.enum import WorkerStatus
from .scoring import score_cluster
from ..util.all_configuration import config_store
from ...custom_logging.models.log_models import RequestLog
from ...custom_logging.util.log_reader import get_avg_latency, get_sent_logs
from datetime import datetime, timezone
from .cluster_data import get_cluster_runtime_data
from ..util.time_utils import compute_simulated_now
from datetime import timedelta
from ...db.postgres import read_model_logs


log = structlog.get_logger()



def _get_simulated_time(config: Config) -> datetime:
    try:
        return compute_simulated_now(
            config.start.start_time_simulated,
            config.start.start_time_real,
        )
    except Exception as e:
        log.warning("global_api.power.simulated_time_fallback_to_now", error=str(e))
        return datetime.now(timezone.utc)


def _get_scored_clusters(
    config: Config,
    clusters: list[ClusterInformation],
    simulated_time: datetime,
) -> list[tuple[float, ClusterInformation, ClusterRuntimeData]]:

    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=config.latency.latency_window_s)
    try:
        recent_requests = read_model_logs(RequestLog, config.id, since=start)
    except Exception:
        recent_requests = []

    avg_latency_by_cluster: dict[str, float] = {}
    for cluster in config.clusters:
        latencies = [r.latency_ms for r in recent_requests if r.cluster == cluster.name]
        avg_latency_by_cluster[cluster.name] = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    scored_clusters = []
    for cluster in clusters:
        runtime_data = get_cluster_runtime_data(
            cluster.cluster_config,
            simulated_time,
            config.energy,
            avg_latency_ms=avg_latency_by_cluster.get(cluster.cluster_config.name),
        )

        cluster_score = score_cluster(
            runtime_data.renewable_output_w,
            runtime_data.cluster_load_w,
            runtime_data.grid_carbon_intensity,
            runtime_data.grid_electricity_price,
            config.weights.gco2,
            config.weights.cost,
            config.weights.latency,
            runtime_data.avg_latency_ms,
            float(config.latency.max_ms),
            config.energy,
        )

        scored_clusters.append((cluster_score, cluster, runtime_data))

    return scored_clusters


def get_current_active_nodes(clusters: list[ClusterInformation]):
    """Analise logs."""
    active_nodes_counter = 0
    for cluster in clusters:
        for worker_node in cluster.worker_nodes:
            status = worker_node.status
            if status == WorkerStatus.WORKING or status == WorkerStatus.IDLE:
                active_nodes_counter += 1
    log.info("global_api.power.active_nodes_counted", active_nodes=active_nodes_counter)
    return active_nodes_counter


def get_current_rps(time_interval_s: int, config_id: str | None) -> float:
    """Return requests per second (RPS) in the last time_interval_s seconds."""
    if not config_id or time_interval_s <= 0:
        return 0.0

    sent = get_sent_logs(config_id, time_interval_s)
    count = len(sent) if sent else 0

    return round(count / time_interval_s, 2)


def estimate_required_nodes(
    avg_latency_per_node_ms: float,
    current_rps: float,
) -> int:
    """Estimate required nodes from demand.

    If avg latency per node is 8000 and the request pr second is 1 (60 request pr minute)
    Then a worker nodes handle 1000/8000=0.125 request pr second.
    Therefore to handle 1 request pr second the required nodes is 1/0.125=8
    """

    if current_rps <= 0:
        log.info("global_api.power.no_current_rps", current_rps=current_rps)
        return 0

    # If we have no valid observed per-node latency, do not attempt to add nodes.
    if avg_latency_per_node_ms <= 0:
        log.info(
            "global_api.power.estimate_missing_latency_no_scale",
            avg_latency_per_node_ms=avg_latency_per_node_ms,
        )
        return 0

    service_rate_rps = 1000.0 / avg_latency_per_node_ms
    required_nodes = math.ceil(current_rps / service_rate_rps)

    return required_nodes


def apply_proportional_scaling(
    current_active_nodes: int,
    avg_latency_ms: float,
    max_latency_ms: float,
) -> int:
    """Calculate nodes to add based on latency scaling alone.

    When avg_latency > max_latency, scale current nodes proportionally.
    Scale factor = avg_latency / max_latency, then subtract current active nodes.
    
    Example: If current=2, avg_latency=16000ms, max_latency=8000ms,
    scale_factor=2, scaled_needed=4, nodes_to_add=4-2=2.
    """
    if max_latency_ms <= 0 or avg_latency_ms <= 0 or current_active_nodes <= 0:
        return 0
    
    if avg_latency_ms > max_latency_ms:
        scale_factor = avg_latency_ms / max_latency_ms
        scaled_nodes_needed = int(math.ceil(current_active_nodes * scale_factor))
        nodes_to_add = scaled_nodes_needed - current_active_nodes
        log.info(
            "global_api.power.proportional_scaling_applied",
            avg_latency_ms=avg_latency_ms,
            max_latency_ms=max_latency_ms,
            scale_factor=round(scale_factor, 2),
            current_active_nodes=current_active_nodes,
            scaled_nodes_needed=scaled_nodes_needed,
            nodes_to_add=nodes_to_add,
        )
        return nodes_to_add
    
    return 0


def estimate_nodes_to_add(
    avg_latency_per_node_ms: float,
    current_rps: float,
    current_active_nodes: int,
) -> int:
    """Estimate how many more worker nodes are needed from lambda and mu."""
    required_nodes = estimate_required_nodes(
        avg_latency_per_node_ms,
        current_rps,
    )

    if current_active_nodes <= 0:
        return max(1, required_nodes)

    nodes_to_add = max(0, required_nodes - current_active_nodes)

    log.info(
        "global_api.power.nodes_to_add_estimated",
        nodes_to_add=nodes_to_add,
        required_nodes=required_nodes,
        current_active_nodes=current_active_nodes,
        current_rps=current_rps,
        avg_latency_per_node_ms=avg_latency_per_node_ms,
    )
    return nodes_to_add


def turn_nodes_on(config: Config, clusters: list[ClusterInformation]):
    """Turn nodes on."""
    # Sort clusters by score (highest first)

    simulated_time = _get_simulated_time(config)
    scored_clusters = _get_scored_clusters(config, clusters, simulated_time)

    sorted_clusters = [
        cluster
        for _, cluster, _ in sorted(scored_clusters, key=lambda item: item[0], reverse=True)
    ]

    avg_latency_ms = get_avg_latency(config.id, config.latency.latency_window_s)
    current_active_nodes = get_current_active_nodes(clusters)
    current_rps = get_current_rps(config.latency.latency_window_s, config.id)
    log.debug(
        "global_api.power.math.variables", 
        current_nodes=current_active_nodes,
        avg_latency_ms=avg_latency_ms,
        current_rps=current_rps,
        max_latency=config.latency.max_ms,
    )
    if current_rps <= 0:
        log.info(
            "global_api.power.skip_turn_on_no_rps",
            current_rps=current_rps,
        )
        return
    if avg_latency_ms <= 0:
        log.info(
            "global_api.power.skip_turn_on_missing_latency",
            avg_latency_ms=avg_latency_ms,
        )
        return

    nodes_to_add = estimate_nodes_to_add(
        avg_latency_ms,
        current_rps,
        current_active_nodes,
    )
    
    # Also calculate nodes needed from latency scaling, use the max of both approaches
    latency_scaling_nodes = apply_proportional_scaling(
        current_active_nodes,
        avg_latency_ms,
        config.latency.max_ms,
    )
    
    nodes_to_add = max(nodes_to_add, latency_scaling_nodes)

    best_cluster_flag = True
    for cluster in sorted_clusters:
        if nodes_to_add <= 0 and not best_cluster_flag:
            break
        powered_off_nodes = 0
        for worker_node in cluster.worker_nodes:
            if worker_node.status == WorkerStatus.OFF:
                powered_off_nodes += 1

        amount = min(nodes_to_add, powered_off_nodes)
        if best_cluster_flag and powered_off_nodes == len(cluster.worker_nodes) and amount <= 0:
            # Always have at least one node on on the best cluster.
            amount = 1

        best_cluster_flag = False
        if amount <= 0:
            continue

        try:
            url = f"http://{cluster.cluster_config.ip}:{cluster.cluster_config.port}/turn_on_nodes/"
            response = requests.post(url, params={"number_of_nodes": amount}, timeout=500)
            response.raise_for_status()
            payload = response.json() if response.content else {}
            turned_on = payload.get("node_changed", amount)
            nodes_to_add -= turned_on
            log.info(
                "global_api.power.turn_on_nodes_requested",
                cluster_name=cluster.cluster_config.name,
                requested=amount,
                turned_on=turned_on,
                nodes_remaining_to_add=nodes_to_add,
            )
        except Exception as e:
            log.error(
                "global_api.power.turn_on_request_failed",
                cluster_name=cluster.cluster_config.name,
                target_url=url,
                error=str(e),
            )


def turn_off_idle_nodes(config: Config):
    """Turn nodes off."""
    avg_latency_ms = get_avg_latency(config.id, config.latency.latency_window_s)
    if avg_latency_ms > config.latency.max_ms:
        log.info(
            "global_api.power.skip_turn_off_latency_above_slo",
            avg_latency_ms=avg_latency_ms,
            max_latency=config.latency.max_ms,
        )
        return

    simulated_time = _get_simulated_time(config)
    scored_clusters = _get_scored_clusters(config, config_store.get_cluster_information(), simulated_time)
    sorted_clusters = [
        cluster
        for _, cluster, _ in sorted(scored_clusters, key=lambda item: item[0], reverse=True)
    ]

    top_cluster_name = sorted_clusters[0].cluster_config.name if sorted_clusters else None

    for cluster in sorted_clusters:
        try:
            url = f"http://{cluster.cluster_config.ip}:{cluster.cluster_config.port}/turn_off_idle_nodes/"
            idle_time = config.power_scheduler.idle_time_for_turn_off_s
            log.debug(
                "global_api.power.turn_off_idle_requested",
                cluster_name=cluster.cluster_config.name,
                idle_time_s=idle_time,
            )
            response = requests.post(
                url,
                params={"idle_time": idle_time, "stay_one": cluster.cluster_config.name == top_cluster_name},
                timeout=500,
            )
            response.raise_for_status()
        except Exception as e:
            log.error(
                "global_api.power.turn_off_idle_request_failed",
                cluster_name=cluster.cluster_config.name,
                target_url=url,
                error=str(e),
            )


async def power_scheduler_loop():
    """Check every x seconds whether more working nodes should be turn on or off."""
    log.info("global_api.power.scheduler_started")
    while True:
        config = config_store.get()
        if config is None:
            log.warning("global_api.power.scheduler_missing_config")
            break

        timeout = config.power_scheduler.timeout_s
        log.info("global_api.power.scheduler_iteration_started", timeout_s=timeout)
        await asyncio.sleep(timeout)
        latest_config = config_store.get()
        if latest_config is None or not latest_config.power_scheduler.start:
            break
        all_clusters = config_store.get_cluster_information()
        turn_nodes_on(latest_config, all_clusters)
        turn_off_idle_nodes(latest_config)
    log.info("global_api.power.scheduler_ended")
