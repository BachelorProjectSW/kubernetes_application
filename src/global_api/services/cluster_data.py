from datetime import datetime, timedelta

import structlog

from ...models.basemodels import ClusterConfig, ClusterRuntimeData, EnergyConfig
from .dk_energy import get_dk_hourly
from .pv_power import get_power
from .price_and_carbon_intensity import fetch_carbon_intensity, fetch_price_data
from .scoring import compute_cluster_load

log = structlog.get_logger()


def get_cluster_runtime_data(
    cluster: ClusterConfig,
    simulated_time_start: datetime,
    energy: EnergyConfig,
) -> ClusterRuntimeData:
    """Fetch all runtime values for a cluster at the given simulated time.

    Args:
        cluster: Static cluster configuration.
        simulated_time_start: Start time for the simulation window.
        energy: Energy configuration constants.

    Returns:
        ClusterRuntimeData with renewable_output_w, cluster_load_w, grid_carbon_intensity,
        and grid_electricity_price.

    """
    simulated_time_end = simulated_time_start + timedelta(hours=1)

    pv = get_power(
        simulated_time_start, simulated_time_end, cluster.simulated_country_code, energy.pv_capacity_w
    )
    renewable_output_w = pv[0][1] if pv else 0.0

    carbon_data = fetch_carbon_intensity(
        simulated_time_start, simulated_time_end, cluster.simulated_country_code
    )
    grid_carbon_intensity = float(carbon_data[0][1]) if carbon_data else 0.0

    # fetch_price_data returns EUR/MWh; scoring expects EUR/kWh so we divide by 1000.
    price_data = fetch_price_data(
        simulated_time_start, simulated_time_end, cluster.simulated_country_code
    )
    grid_electricity_price = (price_data[0][1] / 1000) if price_data else 0.0

    # TODO: replace with actual active/idle node counts once node tracking is implemented
    cluster_load_w = compute_cluster_load(0, 0, energy)

    aau_base_load_data = get_dk_hourly(simulated_time_start, simulated_time_end)
    aau_base_load_w = aau_base_load_data[0]["consumption_w"]

    log.debug(
        "cluster.runtime_data_fetched",
        cluster=cluster.name,
        renewable_output_w=renewable_output_w,
        cluster_load_w=cluster_load_w,
        grid_carbon_intensity=grid_carbon_intensity,
        grid_electricity_price=grid_electricity_price,
    )

    return ClusterRuntimeData(
        renewable_output_w=renewable_output_w,
        cluster_load_w=cluster_load_w,
        grid_carbon_intensity=grid_carbon_intensity,
        grid_electricity_price=grid_electricity_price,
        aau_base_load_w=aau_base_load_w,
    )
