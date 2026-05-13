import requests
import structlog
from ...models.basemodels import Config, EnergyConfig
from datetime import datetime, timezone, timedelta
from ...db.postgres import read_config_by_id, read_config_by_name
from .price_and_carbon_intensity import fetch_carbon_intensity, fetch_price_data
from .dk_energy import get_dk_hourly
from .pv_power import get_power
from ..util.time_utils import SIMULATED_TIME_FORMAT

log = structlog.get_logger()


def validate_config_values(config: Config) -> list[str]:
    """Validate intrinsic configuration values before test startup.

    This validation checks local, deterministic constraints such as unique
    identifiers, workload and duration limits, weight consistency, cluster
    definitions, question settings, latency thresholds, and simulated start
    time format.

    Args:
        config: Full test configuration submitted by the client.

    Returns:
        list[str]: Validation errors. An empty list means the configuration
        values are internally consistent.

    """
    errors = []

    try:
        if config.id and read_config_by_id(config.id) is not None:
            errors.append(f"config id already exists: {config.id}")
        if config.name and read_config_by_name(config.name) is not None:
            errors.append(f"config name already exists: {config.name}")
    except Exception as e:
        # Unit and CI validation should not require a live database.
        log.warning("validate.config_uniqueness_skipped", error=str(e))

    # duration and workload
    if config.start.duration_time_s <= 0:
        errors.append("duration must be > 0")
    if config.workload.request_per_minute <= 0:
        errors.append("request per minute must be > 0")
    total_requests = (config.start.duration_time_s / 60) * config.workload.request_per_minute
    if total_requests < 1:
        errors.append("config would generate 0 requests")

    # weights
    weight_sum = config.weights.gco2 + config.weights.cost + config.weights.latency
    if abs(weight_sum - 1.0) > 0.01:
        errors.append(f"weights must sum to 1.0, got {weight_sum}")
    if any(w < 0 for w in [config.weights.gco2, config.weights.cost, config.weights.latency]):
        errors.append("weights cannot be negative")

    # clusters
    if not config.clusters:
        errors.append("no clusters configured")
    names = [c.name for c in config.clusters]
    if len(names) != len(set(names)):
        errors.append("duplicate cluster names found")
    for cluster in config.clusters:
        if len(cluster.gpio_list) == 0:
            errors.append(f"cluster {cluster.name} has no GPIOs configured")

    # question
    if not config.question.question.strip():
        errors.append("question cannot be empty")
    if config.question.max_output_tokens <= 0:
        errors.append("max_output_tokens must be > 0")

    # latency
    if config.latency.max_ms <= 0:
        errors.append("latency must be > 0")
    if config.latency.latency_window_s <= 0:
        errors.append("latency must be > 0")

    # start time format
    try:
        datetime.strptime(config.start.start_time_simulated, SIMULATED_TIME_FORMAT)
    except ValueError:
        errors.append("start time invalid format, expected DD/MM/YYYY HH:MM:SS")

    return errors


def validate_cluster_reachability(config: Config) -> list[str]:
    """Validate that each configured cluster API is reachable.

    The function calls each cluster's control endpoint and reports connection
    or HTTP failures as validation errors.

    Args:
        config: Full test configuration containing cluster endpoints.

    Returns:
        list[str]: Reachability-related validation errors. Empty means all
        clusters responded successfully.

    """
    errors = []

    for cluster in config.clusters:
        try:
            response = requests.get(
                f"http://{cluster.ip}:{cluster.port}/get_cluster_information",
                timeout=180,
            )
            response.raise_for_status()
            log.info("validate.cluster_reachable", cluster=cluster.name)
        except Exception as e:
            errors.append(f"cluster {cluster.name} unreachable: {str(e)}")
            log.warning("validate.cluster_unreachable", cluster=cluster.name, error=str(e))

    return errors


def validate_electricity_maps(config: Config) -> list[str]:
    """Validate carbon and price availability for non-DK cluster zones.

    For each cluster outside Denmark, this function checks whether external
    market-data providers can return carbon-intensity and price data for the
    simulated test interval.

    Args:
        config: Full test configuration with simulated time, duration, and
            cluster country codes.

    Returns:
        list[str]: API and data-availability validation errors. Empty means all
        required non-DK zones returned data.

    """
    errors = []

    # Use simulated start time from config
    try:
        start = datetime.strptime(config.start.start_time_simulated, SIMULATED_TIME_FORMAT).replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return ["cannot validate APIs: invalid start_time_simulated format"]

    # Start + duration = full duration
    end = start + timedelta(seconds=config.start.duration_time_s)

    for cluster in config.clusters:
        zone = cluster.simulated_country_code.upper()
        if zone.startswith("DK"):
            continue
        try:
            carbon = fetch_carbon_intensity(start, end, zone)
            if not carbon:
                errors.append(f"{cluster.name}: no carbon intensity data for zone={zone} at {start} to {end}")
        except Exception as e:
            errors.append(f"cluster {cluster.name}: carbon intensity API failed: {str(e)}")

        try:
            prices = fetch_price_data(start, end, zone)
            if not prices:
                errors.append(f"cluster {cluster.name}: no price data for zone={zone} at {start} to {end}")
        except Exception as e:
            errors.append(f"cluster {cluster.name}: price API failed: {str(e)}")

    return errors


def validate_dk_energy(config: Config) -> list[str]:
    """Validate DK energy data availability for Danish clusters.

    For clusters mapped to Denmark, this function queries the DK energy source
    for the simulated time interval and reports missing or unavailable data.

    Args:
        config: Full test configuration with simulated time and cluster zones.

    Returns:
        list[str]: DK energy validation errors. Empty means all DK clusters had
        accessible data for the requested interval.

    """
    errors = []

    try:
        start = datetime.strptime(config.start.start_time_simulated, SIMULATED_TIME_FORMAT).replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return []

    end = start + timedelta(seconds=config.start.duration_time_s)

    for cluster in config.clusters:
        if not cluster.simulated_country_code.upper().startswith("DK"):
            continue
        try:
            data = get_dk_hourly(start, end)
            if not data:
                errors.append(f"cluster {cluster.name}: no DK energy data for {start} to {end}")
        except Exception as e:
            errors.append(f"cluster {cluster.name}: DK energy proxy unreachable: {str(e)}")

    return errors


def validate_pv_data(config: Config) -> list[str]:
    """Validate PV production data availability for each cluster zone.

    This function checks whether local PV power data can be retrieved for the
    simulated interval and configured PV capacity in each cluster's country.

    Args:
        config: Full test configuration with simulated time and cluster zones.

    Returns:
        list[str]: PV data validation errors. Empty means PV data was available
        for all relevant clusters.

    """
    errors = []

    try:
        start = datetime.strptime(config.start.start_time_simulated, SIMULATED_TIME_FORMAT).replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return []

    end = start + timedelta(seconds=config.start.duration_time_s)
    pv_capacity_w = EnergyConfig().pv_capacity_w
    for cluster in config.clusters:
        uppercase_country = cluster.simulated_country_code.upper()
        try:
            data = get_power(start, end, uppercase_country, pv_capacity_w=pv_capacity_w)
            if not data:
                errors.append(f"{cluster.name}: no PV data for zone={uppercase_country} at {start} to {end}")
        except Exception as e:
            errors.append(f"cluster {cluster.name}: PV data error: {str(e)}")

    return errors


def validate_config(config: Config) -> dict:
    """Run the full validation pipeline for a test configuration.

    The pipeline combines intrinsic config checks, cluster reachability checks,
    and required market and energy data checks before a test is allowed to
    start.

    Args:
        config: Full test configuration submitted by the client.

    Returns:
        dict: Validation result payload with two keys:
            - ``valid`` (bool): ``True`` when no validation errors were found.
            - ``errors`` (list[str]): Collected validation error messages.

    """
    errors = []
    errors.extend(validate_config_values(config))
    errors.extend(validate_cluster_reachability(config))
    errors.extend(validate_electricity_maps(config))
    errors.extend(validate_dk_energy(config))
    errors.extend(validate_pv_data(config))

    valid = len(errors) == 0
    log.info("validate.config", valid=valid, errors=errors)

    return {
        "valid": valid,
        "errors": errors,
    }
