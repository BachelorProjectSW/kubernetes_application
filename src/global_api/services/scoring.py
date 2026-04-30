from ...models.basemodels import ClusterConfig, ClusterRuntimeData, EnergyConfig, WeightsConfig
import structlog


log = structlog.get_logger()


def compute_cluster_load(active_nodes: int, idle_nodes: int, energy: EnergyConfig) -> float:
    """Compute cluster power consumption in watts when scaled.

    Args:
        active_nodes: Number of nodes currently running workload.
        idle_nodes: Number of nodes on but not running workload.
        energy: Energy configuration constants.

    Returns:
        Total cluster load in watts.

    """
    active_power = active_nodes * energy.node_power_active_w * energy.power_scale_factor
    idle_power = idle_nodes * energy.node_power_idle_w * energy.power_scale_factor
    return active_power + idle_power


def compute_grid_fraction(renewable_output_w: float, cluster_load_w: float) -> float:
    """Compute what fraction of the cluster's power comes from the grid.

    Args:
        renewable_output_w: Current renewable production in watts.
        cluster_load_w: Current cluster power consumption in watts.

    Returns:
        Grid fraction between 0.0 (fully renewable) and 1.0 (fully grid).

    """
    if cluster_load_w <= 0:
        return 0.0

    renewable_fraction = min((renewable_output_w / cluster_load_w), 1.0)
    return 1.0 - renewable_fraction


def compute_carbon_blend(
    renewable_output_w: float, cluster_load_w: float, grid_carbon_intensity: float
) -> float:
    """Compute blended carbon intensity accounting for microgrid production.

    Args:
        renewable_output_w: Current renewable production in watts.
        cluster_load_w: Current cluster power consumption in watts.
        grid_carbon_intensity: Carbon intensity (gCO2/kWh) of the grid.

    Returns:
        Blended carbon intensity in gCO2/kWh.

    """
    grid_fraction = compute_grid_fraction(renewable_output_w, cluster_load_w)
    return grid_carbon_intensity * grid_fraction


def compute_cost_blend(
    renewable_output_w: float, cluster_load_w: float, grid_electricity_price: float
) -> float:
    """Compute blended energy cost accounting for microgrid production.

    Args:
        renewable_output_w: Current renewable production in watts.
        cluster_load_w: Current cluster power consumption in watts.
        grid_electricity_price: Current grid electricity price (EUR/kWh).

    Returns:
        Blended electricity price in EUR/kWh.

    """
    grid_fraction = compute_grid_fraction(renewable_output_w, cluster_load_w)
    return round(grid_electricity_price * grid_fraction, 4)


def normalize_value(value: float, ref_max: float) -> float:
    """Normalize a value against its maximum value.

    Args:
        value: value to be normalized.
        ref_max: the worst realistic value.

    Returns:
        A normalized value between 0.0 (worst) and 1.0 (best).

    """
    score = 1.0 - (value / ref_max)
    return round(max(score, 0.0), 4)


def score_cluster(
    renewable_output_w: float,
    cluster_load_w: float,
    grid_carbon_intensity: float,
    grid_electricity_price: float,
    carbon_weight: float,
    cost_weight: float,
    latency_weight: float,
    estimated_latency_ms: float,
    max_latency_ms: float,
    energy: EnergyConfig,
) -> float:
    """Compute the score for a cluster.

    The score is a weighted sum of three normalized objectives — carbon intensity,
    electricity cost, and request latency — each mapped to [0, 1] where 1 is best.
    Latency is normalized against the user-specified SLO (max_latency_ms), so a
    cluster at the latency limit scores 0 and a cluster with no observed latency
    scores 1. This follows the Weighted Sum Model (WSM) for multi-criteria
    decision making (Hwang & Yoon, 1981).

    Args:
        renewable_output_w: Current renewable production in watts.
        cluster_load_w: Current cluster power consumption in watts.
        grid_carbon_intensity: Carbon intensity (gCO2/kWh) of the grid.
        grid_electricity_price: Current grid electricity price (EUR/kWh).
        carbon_weight: Weight specified by the user on carbon.
        cost_weight: Weight specified by the user on cost.
        latency_weight: Weight specified by the user on latency.
        estimated_latency_ms: Average observed latency for this cluster over the recent window (ms).
        max_latency_ms: User-specified maximum acceptable latency (ms).
        energy: Energy configuration constants.

    Returns:
        Score between 1.0 and 0.0. Higher is best.

    """
    blended_carbon = compute_carbon_blend(
        renewable_output_w,
        cluster_load_w,
        grid_carbon_intensity,
    )
    blended_cost = compute_cost_blend(
        renewable_output_w,
        cluster_load_w,
        grid_electricity_price,
    )

    norm_carbon = normalize_value(blended_carbon, energy.carbon_ref_max)
    norm_cost = normalize_value(blended_cost, energy.cost_ref_max)
    norm_latency = normalize_value(estimated_latency_ms, max_latency_ms)

    return round(
        (carbon_weight * norm_carbon)
        + (cost_weight * norm_cost)
        + (latency_weight * norm_latency),
        4,
    )


# TODO jeg tror ikke den tager højde for at den ikke
# sender request ud til at cluster med kun slukkede worker nodes.
# TODO Så derfor sikre sig at der er nogle tændte og hvis ikke så tænd nogle inden:D
def choose_cluster(
    clusters: list[ClusterConfig],
    cluster_energy_data_list: list[ClusterRuntimeData],
    weights: WeightsConfig,
    energy: EnergyConfig,
    max_latency_ms: float,
) -> tuple[ClusterConfig, ClusterRuntimeData]:
    """Choose the best cluster based on scoring.

    Args:
        clusters: List of static cluster configurations.
        cluster_energy_data_list: Runtime values for each cluster, in the same order as clusters.
        weights: User-specified carbon, cost, and latency weights.
        energy: Energy configuration constants.
        max_latency_ms: User-specified maximum acceptable latency (ms).

    Returns:
        Tuple of (best ClusterConfig, its ClusterRuntimeData).

    """
    best_cluster = None
    best_cluster_energy_data = None
    best_score = -1.0

    for cluster, cluster_energy_data in zip(clusters, cluster_energy_data_list):
        if cluster_energy_data.all_nodes_powered_off:
            # No active nodes on cluster
            continue
        cluster_score = score_cluster(
            cluster_energy_data.renewable_output_w,
            cluster_energy_data.cluster_load_w,
            cluster_energy_data.grid_carbon_intensity,
            cluster_energy_data.grid_electricity_price,
            weights.gco2,
            weights.cost,
            weights.latency,
            cluster_energy_data.avg_latency_ms,
            max_latency_ms,
            energy,
        )

        log.debug(
            "global_api.cluster.scored",
            cluster_name=cluster.name,
            score=cluster_score,
            renewable_output_w=cluster_energy_data.renewable_output_w,
            grid_electricity_price=cluster_energy_data.grid_electricity_price,
        )

        if cluster_score > best_score:
            best_score = cluster_score
            best_cluster = cluster
            best_cluster_energy_data = cluster_energy_data

    log.info(
        "global_api.cluster.selected",
        cluster_name=best_cluster.name,
        score=best_score,
    )

    return best_cluster, best_cluster_energy_data
