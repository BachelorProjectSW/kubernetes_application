from ...models.basemodels import ClusterConfig, WeightsConfig
import structlog
from global_api.config.energy_config import (
    CARBON_REF_MAX,
    COST_REF_MAX,
    NODE_POWER_IDLE_W,
    NODE_POWER_ACTIVE_W,
    POWER_SCALE_FACTOR,
)


log = structlog.get_logger()


def compute_cluster_load(active_nodes: int, idle_nodes: int) -> float:
    """Compute cluster power consumption in watts when scaled.

    Args:
        active_nodes: Number of nodes currently running workload.
        idle_nodes: Number of nodes on but not running workload.

    Returns:
        Total cluster load in watts.

    """
    active_power = active_nodes * NODE_POWER_ACTIVE_W * POWER_SCALE_FACTOR
    idle_power = idle_nodes * NODE_POWER_IDLE_W * POWER_SCALE_FACTOR
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
) -> float:
    """Compute the score for a cluster.

    Args:
        renewable_output_w: Current renewable production in watts.
        cluster_load_w: Current cluster power consumption in watts.
        grid_carbon_intensity: Carbon intensity (gCO2/kWh) of the grid.
        grid_electricity_price: Current grid electricity price (EUR/kWh).
        carbon_weight: weight specified by the user on carbon.
        cost_weight: weight specified by the user on cost.

    Returns:
        Score between 1.0 and 0.0. Higher is best.

    """
    blended_carbon = compute_carbon_blend(renewable_output_w, cluster_load_w, grid_carbon_intensity)
    blended_cost = compute_cost_blend(renewable_output_w, cluster_load_w, grid_electricity_price)

    blended_carbon_normalized = normalize_value(blended_carbon, CARBON_REF_MAX)
    blended_cost_normalized = normalize_value(blended_cost, COST_REF_MAX)

    return round((carbon_weight * blended_carbon_normalized) + (cost_weight * blended_cost_normalized), 4)


def choose_cluster(clusters: list[ClusterConfig], weights: WeightsConfig):
    """Choose the best cluster based on scoring.

    Returns:
        The cluster dict with the highest score.

    """
    best_cluster = None
    best_score = -1.0

    for cluster in clusters:
        cluster_score = score_cluster(
            cluster.renewable_output_w,
            cluster.cluster_load_w,
            cluster.grid_carbon_intensity,
            cluster.grid_electricity_price,
            weights.gco2,
            weights.cost,
        )

        log.debug(
            "cluster.scored",
            cluster=cluster.name,
            score=cluster_score,
            renewable_output_w=cluster.renewable_output_w,
            grid_electricity_price=cluster.grid_electricity_price,
        )

        if cluster_score > best_score:
            best_score = cluster_score
            best_cluster = cluster

    log.info(
        "cluster.selected",
        cluster=best_cluster.name,
        score=best_score,
    )

    return best_cluster
