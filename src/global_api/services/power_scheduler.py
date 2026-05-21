import math
import requests
import structlog
import asyncio
from ...models.basemodels import Config, ClusterInformation, ClusterRuntimeData
from ...models.enum import WorkerStatus
from .scoring import score_cluster
from ..util.all_configuration import config_store
from ...custom_logging.models.log_models import RequestLog
from ...custom_logging.util.log_reader import get_avg_latency, get_sent_logs, get_avg_llama_latency
from datetime import datetime, timezone
from .cluster_data import get_cluster_runtime_data
from ..util.time_utils import compute_simulated_now
from datetime import timedelta
from ...db.postgres import read_model_logs


log = structlog.get_logger()


def _get_simulated_time(config: Config) -> datetime:
    """Return the simulated current time for the active test run.

    Args:
        config: Current scheduler configuration.

    Returns:
        The current simulated time.

    """
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
    """Build a score for each cluster using its current runtime data.

    Args:
        config: Current scheduler configuration.
        clusters: Cluster metadata with worker nodes.
        simulated_time: Current simulated time used for energy lookup.

    Returns:
        A list of scored clusters and their runtime data.

    """
    # Read recent request logs once so every cluster uses the same latency view.
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=config.latency.latency_window_s)
    try:
        recent_requests = read_model_logs(RequestLog, config.id, since=start)
    except Exception:
        recent_requests = []

    # Turn the recent request history into one average latency per cluster.
    avg_latency_by_cluster: dict[str, float] = {}
    for cluster in config.clusters:
        latencies = [r.latency_ms for r in recent_requests if r.cluster == cluster.name]
        avg_latency_by_cluster[cluster.name] = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    # Gather runtime energy data and compute a score for each cluster.
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
            config.energy,
        )

        scored_clusters.append((cluster_score, cluster, runtime_data))

    return scored_clusters


def get_current_active_nodes(clusters: list[ClusterInformation]):
    """Count worker nodes that are currently on or active.

    Args:
        clusters: Cluster metadata with worker nodes.

    Returns:
        Number of worker nodes that are on.

    """
    active_nodes_counter = 0
    for cluster in clusters:
        for worker_node in cluster.worker_nodes:
            status = worker_node.status
            if status == WorkerStatus.WORKING or status == WorkerStatus.IDLE:
                active_nodes_counter += 1
    log.info("global_api.power.active_nodes_counted", active_nodes=active_nodes_counter)
    return active_nodes_counter


def get_current_rps(time_interval_s: int, config_id: str | None) -> float:
    """Return requests per second (RPS) for the given time window.

    This is received by the workload scheduler who log when a request is sent.
    This could be discussed whether it should be on when its received on global api.

    Args:
        time_interval_s: Number of seconds to look back.
        config_id: Optional configuration id for the current run.

    Returns:
        Requests per second in the selected time window.

    """
    if not config_id or time_interval_s <= 0:
        return 0.0

    sent = get_sent_logs(config_id, time_interval_s)
    count = len(sent) if sent else 0

    return round(count / time_interval_s, 2)


def estimate_required_nodes(
    avg_llama_latency_ms: float,
    current_rps: float,
) -> int:
    """Estimate how many nodes are needed from current demand.

    If avg latency per node is 8000 and the request pr second is 1 (60 request pr minute)
    Then a worker nodes handle 1000/8000=0.125 request pr second.
    Therefore to handle 1 request pr second the required nodes is 1/0.125=8

    Args:
        avg_llama_latency_ms: Average observed latency for one node.
        current_rps: Current requests per second.

    Returns:
        Estimated number of nodes needed to handle the demand.

    """
    if current_rps <= 0:
        log.info("global_api.power.no_current_rps", current_rps=current_rps)
        return 0

    # If we have no valid observed per-node latency, do not attempt to add nodes.
    if avg_llama_latency_ms <= 0:
        log.info(
            "global_api.power.estimate_missing_latency_no_scale",
            avg_llama_latency_ms=avg_llama_latency_ms,
        )
        return 0

    service_rate_rps = 1000.0 / avg_llama_latency_ms
    required_nodes = math.ceil(current_rps / service_rate_rps)

    return required_nodes


def apply_lantecy_scaling(
    current_active_nodes: int,
    avg_latency_ms: float,
    max_latency_ms: float,
) -> int:
    """Calculate extra nodes needed when latency is above the limit.

    When avg_latency > max_latency, scale current nodes proportionally.
    Scale factor = avg_latency / max_latency, then subtract current active nodes.

    Example: If current=2, avg_latency=16000ms, max_latency=8000ms,
    scale_factor=2, scaled_needed=4, nodes_to_add=4-2=2.

    Args:
        current_active_nodes: Number of nodes currently active.
        avg_latency_ms: Average observed latency.
        max_latency_ms: Maximum acceptable latency.

    Returns:
        Number of extra nodes to add from latency scaling.

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
    avg_llama_latency_ms: float,
    current_rps: float,
    current_active_nodes: int,
) -> int:
    """Estimate how many additional worker nodes should be turned on.

    Args:
        avg_llama_latency_ms: Average observed latency for one node.
        current_rps: Current requests per second.
        current_active_nodes: Number of worker nodes already on.

    Returns:
        Number of additional worker nodes to power on.

    """
    required_nodes = estimate_required_nodes(
        avg_llama_latency_ms,
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
        avg_llama_latency_ms=avg_llama_latency_ms,
    )
    return nodes_to_add


def turn_nodes_on(config: Config, clusters: list[ClusterInformation]):
    """Turn on worker nodes when demand or latency requires more capacity.

    Args:
        config: Current scheduler configuration.
        clusters: Cluster information and worker node state.

    Returns:
        None.

    """
    # Start from the current simulated time and score every cluster.
    simulated_time = _get_simulated_time(config)
    scored_clusters = _get_scored_clusters(config, clusters, simulated_time)

    # Process the best-scoring clusters first.
    sorted_clusters = [
        cluster
        for _, cluster, _ in sorted(scored_clusters, key=lambda item: item[0], reverse=True)
    ]

    # Read the current demand and latency signals before deciding to scale.
    avg_llama_latency_ms = get_avg_llama_latency(config.id, config.latency.latency_window_s)
    current_active_nodes = get_current_active_nodes(clusters)
    current_rps = get_current_rps(config.latency.latency_window_s, config.id)
    log.debug(
        "global_api.power.math.variables",
        current_nodes=current_active_nodes,
        avg_llama_latency_ms=avg_llama_latency_ms,
        current_rps=current_rps,
        max_latency=config.latency.max_ms,
    )
    if current_rps <= 0:
        log.info(
            "global_api.power.skip_turn_on_no_rps",
            current_rps=current_rps,
        )
        return
    if avg_llama_latency_ms <= 0:
        log.info(
            "global_api.power.skip_turn_on_missing_latency",
            avg_llama_latency_ms=avg_llama_latency_ms,
        )
        return

    # Estimate the scale-up need from throughput, then take the larger one.
    nodes_to_add = estimate_nodes_to_add(
        avg_llama_latency_ms,
        current_rps,
        current_active_nodes,
    )

    # Also calculate nodes needed from latency scaling, then keep the larger estimate.
    latency_scaling_nodes = apply_lantecy_scaling(
        current_active_nodes,
        avg_llama_latency_ms,
        config.latency.max_ms,
    )

    nodes_to_add = max(nodes_to_add, latency_scaling_nodes)

    for cluster in sorted_clusters:
        if nodes_to_add <= 0:
            break
        powered_off_nodes = 0
        for worker_node in cluster.worker_nodes:
            if worker_node.status == WorkerStatus.OFF:
                powered_off_nodes += 1

        amount = min(nodes_to_add, powered_off_nodes)

        if amount <= 0:
            continue

        try:
            # Ask the selected cluster to power on only the number of OFF nodes needed.
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
    """Turn off idle worker nodes when latency is healthy enough.

    Args:
        config: Current scheduler configuration.

    Returns:
        None.

    """
    avg_latency_ms = get_avg_latency(config.id, config.latency.latency_window_s)
    if avg_latency_ms > config.latency.max_ms:
        log.info(
            "global_api.power.skip_turn_off_latency_above_slo",
            avg_latency_ms=avg_latency_ms,
            max_latency=config.latency.max_ms,
        )
        return

    for cluster in config.clusters:
        try:
            # Ask each cluster to shut down nodes that have stayed idle long enough.
            url = f"http://{cluster.ip}:{cluster.port}/turn_off_idle_nodes/"
            idle_time = config.power_scheduler.idle_time_for_turn_off_s
            log.debug(
                "global_api.power.turn_off_idle_requested",
                cluster_name=cluster.name,
                idle_time_s=idle_time,
            )
            response = requests.post(
                url,
                params={"idle_time": idle_time},
                timeout=500,
            )
            response.raise_for_status()
        except Exception as e:
            log.error(
                "global_api.power.turn_off_idle_request_failed",
                cluster_name=cluster.name,
                target_url=url,
                error=str(e),
            )


async def power_scheduler_loop():
    """Periodically decide whether the cluster should scale up or down.

    Returns:
        None.

    """
    log.info("global_api.power.scheduler_started")
    while True:
        # Stop early if the scheduler has no active configuration.
        config = config_store.get()
        if config is None:
            log.warning("global_api.power.scheduler_missing_config")
            break

        # Wait for the configured interval before evaluating the next cycle.
        timeout = config.power_scheduler.timeout_s
        log.info("global_api.power.scheduler_iteration_started", timeout_s=timeout)
        await asyncio.sleep(timeout)

        # Re-read the config in case the test was stopped.
        latest_config = config_store.get()
        if latest_config is None or not latest_config.power_scheduler.start:
            break

        # Turn nodes on first, then try turning off idle nodes with the same config.
        all_clusters = config_store.get_cluster_information()
        turn_nodes_on(latest_config, all_clusters)
        turn_off_idle_nodes(latest_config)
    log.info("global_api.power.scheduler_ended")
