from datetime import datetime, timedelta
import threading
import time

import structlog

from ...models.basemodels import ClusterConfig, ClusterRuntimeData, EnergyConfig
from .dk_energy import get_dk_hourly
from .pv_power import get_power
from .price_and_carbon_intensity import fetch_carbon_intensity, fetch_price_data
from .scoring import compute_cluster_load
from ...custom_logging.util.log_reader import get_avg_latency_for_cluster

log = structlog.get_logger()


# Hourly cache for market data only.
# Key format: (zone_upper, start_hour_iso, end_hour_iso)
_carbon_hourly_cache: dict[tuple[str, str, str], list[tuple[datetime, int]]] = {}
_price_hourly_cache: dict[tuple[str, str, str], list[tuple[datetime, float]]] = {}

# Per-key locks prevent cache stampede when many requests hit a cold cache at once.
_market_cache_lock = threading.Lock()
_carbon_locks: dict[tuple[str, str, str], threading.Lock] = {}
_price_locks: dict[tuple[str, str, str], threading.Lock] = {}

# Short TTL cache for DB-backed latency lookups.
_latency_cache: dict[tuple[str, int], tuple[float, float]] = {}
_latency_cache_lock = threading.Lock()
_LATENCY_CACHE_TTL_S = 3.0


def _hour_floor(value: datetime) -> datetime:
    """Round down to the start of the hour."""
    return value.replace(minute=0, second=0, microsecond=0)


def _hourly_cache_key(zone: str, start: datetime, end: datetime) -> tuple[str, str, str]:
    """Build cache key based on zone and hour-normalized time range."""
    start_hour = _hour_floor(start)
    end_hour = _hour_floor(end)
    return zone.upper(), start_hour.isoformat(), end_hour.isoformat()


def _get_hourly_cached_carbon(start: datetime, end: datetime, zone: str) -> list[tuple[datetime, int]]:
    """Return hourly carbon data from cache when available, else fetch and store."""
    key = _hourly_cache_key(zone, start, end)
    cached = _carbon_hourly_cache.get(key)
    if cached is not None:
        return cached

    with _market_cache_lock:
        lock = _carbon_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _carbon_locks[key] = lock

    with lock:
        cached = _carbon_hourly_cache.get(key)
        if cached is not None:
            return cached

        data = fetch_carbon_intensity(start, end, zone)
        _carbon_hourly_cache[key] = data
        return data


def _get_hourly_cached_price(start: datetime, end: datetime, zone: str) -> list[tuple[datetime, float]]:
    """Return hourly price data from cache when available, else fetch and store."""
    key = _hourly_cache_key(zone, start, end)
    cached = _price_hourly_cache.get(key)
    if cached is not None:
        return cached

    with _market_cache_lock:
        lock = _price_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _price_locks[key] = lock

    with lock:
        cached = _price_hourly_cache.get(key)
        if cached is not None:
            return cached

        data = fetch_price_data(start, end, zone)
        _price_hourly_cache[key] = data
        return data


def _get_cached_avg_latency_ms(cluster_name: str, latency_window_s: int) -> float:
    """Return recently computed avg latency to avoid repeated DB scans per burst."""
    now = time.monotonic()
    key = (cluster_name, latency_window_s)

    with _latency_cache_lock:
        cached = _latency_cache.get(key)
        if cached is not None:
            expires_at, value = cached
            if now < expires_at:
                return value

    value = get_avg_latency_for_cluster(cluster_name, latency_window_s)
    with _latency_cache_lock:
        _latency_cache[key] = (now + _LATENCY_CACHE_TTL_S, value)
    return value


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

    pv = get_power(
        simulated_time_start, simulated_time_end, cluster.simulated_country_code, energy.pv_capacity_w
    )
    renewable_output_w = pv[0][1] if pv else 0.0

    carbon_data = _get_hourly_cached_carbon(
        simulated_time_start, simulated_time_end, cluster.simulated_country_code
    )
    grid_carbon_intensity = float(carbon_data[0][1]) if carbon_data else 0.0

    # fetch_price_data returns EUR/MWh; scoring expects EUR/kWh so we divide by 1000.
    price_data = _get_hourly_cached_price(
        simulated_time_start, simulated_time_end, cluster.simulated_country_code
    )
    grid_electricity_price = (price_data[0][1] / 1000) if price_data else 0.0

    # TODO: replace with actual active/idle node counts once node tracking is implemented
    cluster_load_w = compute_cluster_load(0, 0, energy)

    microgrid_base_load_w = _get_microgrid_base_load_w(
        cluster,
        simulated_time_start,
        simulated_time_end,
    )
    cluster_load_w += microgrid_base_load_w

    avg_latency_ms = _get_cached_avg_latency_ms(cluster.name, latency_window_s)

    log.debug(
        "global_api.cluster.runtime_data_fetched",
        cluster_name=cluster.name,
        renewable_output_w=renewable_output_w,
        cluster_load_w=cluster_load_w,
        microgrid_base_load_w=microgrid_base_load_w,
        grid_carbon_intensity=grid_carbon_intensity,
        grid_electricity_price=grid_electricity_price,
        avg_latency_ms=avg_latency_ms,
    )

    return ClusterRuntimeData(
        renewable_output_w=renewable_output_w,
        cluster_load_w=cluster_load_w,
        grid_carbon_intensity=grid_carbon_intensity,
        grid_electricity_price=grid_electricity_price,
        avg_latency_ms=avg_latency_ms,
    )
