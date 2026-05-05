from datetime import datetime, timedelta, timezone
import requests
import structlog

from ...models.basemodels import ClusterConfig, ClusterRuntimeData, EnergyConfig, WorkerNode
from ...models.enum import WorkerStatus
from .dk_energy import get_dk_hourly
from .scoring import compute_cluster_load
from ...custom_logging.models.log_models import MarketSnapshotLog
from ...db.postgres import save_model_log
from ..util.all_configuration import config_store
from ..util.market_data_store import market_data_store

log = structlog.get_logger()

_logged_market_hours: set[tuple[str, str, datetime]] = set()


def _log_market_snapshot_if_new(
    cluster_name: str,
    simulated_hour: datetime,
    carbon_gco2_per_kwh: float,
    cost_eur_per_kwh: float,
) -> None:
    """Write a MarketSnapshotLog entry for this cluster and hour if not already written."""
    config = config_store.get()
    if config is None or config.id is None:
        return

    key = (config.id, cluster_name, simulated_hour)
    if key in _logged_market_hours:
        return

    _logged_market_hours.add(key)
    save_model_log(
        config.id,
        MarketSnapshotLog(
            timestamp=datetime.now(timezone.utc),
            simulated_hour=simulated_hour,
            cluster=cluster_name,
            carbon_gco2_per_kwh=carbon_gco2_per_kwh,
            cost_eur_per_kwh=cost_eur_per_kwh,
        ),
    )


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
            return float(dk_hourly[0]["avg_consumption_w"])
        case _:
            return 0.0


def get_cluster_runtime_data(
    cluster: ClusterConfig,
    simulated_time_start: datetime,
    energy: EnergyConfig,
    avg_latency_ms: float | None = None,
) -> ClusterRuntimeData:
    """Fetch all runtime values for a cluster at the given simulated time.

    Args:
        cluster: Static cluster configuration.
        simulated_time_start: Start time for the simulation window.
        energy: Energy configuration constants.
        avg_latency_ms: Clusters avg latency.

    Returns:
        ClusterRuntimeData with renewable_output_w, cluster_load_w,
        grid_carbon_intensity, grid_electricity_price, and avg_latency_ms.

    """
    try:
        simulated_time_end = simulated_time_start + timedelta(hours=1)

        pv = market_data_store.get_power(
            simulated_time_start, simulated_time_end, cluster.simulated_country_code, energy.pv_capacity_w
        )
        renewable_output_w = pv[0][1] if pv else 0.0

        carbon_data = market_data_store.get_carbon(
            simulated_time_start, simulated_time_end, cluster.simulated_country_code
        )
        grid_carbon_intensity = float(carbon_data[0][1]) if carbon_data else 0.0

        price_data = market_data_store.get_price(
            simulated_time_start, simulated_time_end, cluster.simulated_country_code
        )
        grid_electricity_price = (price_data[0][1] / 1000) if price_data else 0.0

        
        simulated_hour = simulated_time_start.replace(minute=0, second=0, microsecond=0)
        _log_market_snapshot_if_new(
            cluster.name,
            simulated_hour,
            grid_carbon_intensity,
            grid_electricity_price,
        )

        url = f"http://{cluster.ip}:{cluster.port}/get_cluster_working_nodes"
        response = requests.get(url, timeout=180)
        response.raise_for_status()
        worker_nodes_payload = response.json()
        active_nodes = 0
        idle_nodes = 0

        for node_data in worker_nodes_payload:
            worker_node = WorkerNode.model_validate(node_data)
            if worker_node.status == WorkerStatus.WORKING:
                active_nodes += 1
            elif worker_node.status == WorkerStatus.IDLE:
                idle_nodes += 1

        cluster_load_w = compute_cluster_load(active_nodes, idle_nodes, energy)

        microgrid_base_load_w = _get_microgrid_base_load_w(
            cluster,
            simulated_time_start,
            simulated_time_end,
        )
        cluster_load_w += microgrid_base_load_w

        log.info(
            "global_api.cluster.runtime_data_timing",
            service="global_api",
            cluster_name=cluster.name,
            simulated_time_start=simulated_time_start.isoformat(),
            simulated_time_end=simulated_time_end.isoformat(),
            active_nodes=active_nodes,
            idle_nodes=idle_nodes,
        )
        all_nodes_powered_off = active_nodes == 0 and idle_nodes == 0

        return ClusterRuntimeData(
            renewable_output_w=renewable_output_w,
            cluster_load_w=cluster_load_w,
            grid_carbon_intensity=grid_carbon_intensity,
            grid_electricity_price=grid_electricity_price,
            avg_latency_ms=avg_latency_ms,
            all_nodes_powered_off=all_nodes_powered_off

        )

    except Exception as e:
        log.warning("global_api.cluster_data", cluster_name=cluster.name, error=str(e))
        raise
