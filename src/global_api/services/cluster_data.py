from datetime import datetime, timedelta
import time

import structlog

from ...models.basemodels import ClusterConfig, ClusterRuntimeData, EnergyConfig
from .dk_energy import get_dk_hourly
from .scoring import compute_cluster_load
from ...custom_logging.util.log_reader import get_avg_latency_for_cluster
from ..util.market_data_store import market_data_store

log = structlog.get_logger()


def _get_microgrid_base_load_w(
    cluster: ClusterConfig,
    simulated_time_start: datetime,
    simulated_time_end: datetime,
) -> float:
    """Return extra base load for clusters backed by real microgrid data."""
    country_code = cluster.simulated_country_code.upper()

    match country_code:
        case code if code.startswith("DK"):
            dk_hourly = get_dk_hourly(simulated_time_start, simulated_time_end)
            return float(dk_hourly[0]["consumption_w"])
        case _:
            return 0.0


def get_cluster_runtime_data(
    cluster: ClusterConfig,
    simulated_time_start: datetime,
    energy: EnergyConfig,
    latency_window_s: int,
) -> ClusterRuntimeData:
    """Fetch all runtime values for a cluster at the given simulated time.

    Args:
        cluster: Static cluster configuration.
        simulated_time_start: Start time for the simulation window.
        energy: Energy configuration constants.
        latency_window_s: How far back to look when computing the average latency
                          for this cluster (seconds).

    Returns:
        ClusterRuntimeData with renewable_output_w, cluster_load_w,
        grid_carbon_intensity, grid_electricity_price, and avg_latency_ms.

    """
    simulated_time_end = simulated_time_start + timedelta(hours=1)
    runtime_start = time.monotonic()

    pv_start = time.monotonic()
    pv = market_data_store.get_power(
        simulated_time_start, simulated_time_end, cluster.simulated_country_code, energy.pv_capacity_w
    )
    renewable_output_w = pv[0][1] if pv else 0.0
    pv_fetch_ms = int((time.monotonic() - pv_start) * 1000)

    carbon_start = time.monotonic()
    carbon_data = market_data_store.get_carbon(
        simulated_time_start, simulated_time_end, cluster.simulated_country_code
    )
    grid_carbon_intensity = float(carbon_data[0][1]) if carbon_data else 0.0
    carbon_fetch_ms = int((time.monotonic() - carbon_start) * 1000)

    # fetch_price_data returns EUR/MWh; scoring expects EUR/kWh so we divide by 1000.
    price_start = time.monotonic()
    price_data = market_data_store.get_price(
        simulated_time_start, simulated_time_end, cluster.simulated_country_code
    )
    grid_electricity_price = (price_data[0][1] / 1000) if price_data else 0.0
    price_fetch_ms = int((time.monotonic() - price_start) * 1000)

    # TODO: replace with actual active/idle node counts once node tracking is implemented
    load_start = time.monotonic()
    cluster_load_w = compute_cluster_load(0, 0, energy)

    microgrid_base_load_w = _get_microgrid_base_load_w(
        cluster,
        simulated_time_start,
        simulated_time_end,
    )
    cluster_load_w += microgrid_base_load_w
    load_compute_ms = int((time.monotonic() - load_start) * 1000)

    latency_start = time.monotonic()
    avg_latency_ms = get_avg_latency_for_cluster(cluster.name, latency_window_s)
    latency_lookup_ms = int((time.monotonic() - latency_start) * 1000)

    total_runtime_data_ms = int((time.monotonic() - runtime_start) * 1000)

    log.info(
        "global_api.cluster.runtime_data_timing",
        service="global_api",
        cluster_name=cluster.name,
        pv_fetch_ms=pv_fetch_ms,
        carbon_fetch_ms=carbon_fetch_ms,
        price_fetch_ms=price_fetch_ms,
        load_compute_ms=load_compute_ms,
        latency_lookup_ms=latency_lookup_ms,
        total_runtime_data_ms=total_runtime_data_ms,
    )

    return ClusterRuntimeData(
        renewable_output_w=renewable_output_w,
        cluster_load_w=cluster_load_w,
        grid_carbon_intensity=grid_carbon_intensity,
        grid_electricity_price=grid_electricity_price,
        avg_latency_ms=avg_latency_ms,
    )
