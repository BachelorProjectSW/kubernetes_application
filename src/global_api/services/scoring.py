CARBON_REF_MAX = 800  # gCO2/kWh (need to find reference for)
COST_REF_MAX = 0.30  # EUR/kWh (need to find reference for)


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
