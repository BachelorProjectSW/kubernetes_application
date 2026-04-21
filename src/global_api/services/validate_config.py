import requests
import structlog
from ...models.basemodels import Config, EnergyConfig

log = structlog.get_logger()
from datetime import datetime, timezone, timedelta
from .price_and_carbon_intensity import fetch_carbon_intensity, fetch_price_data
from .dk_energy import get_dk_hourly
from .pv_power import get_power

def validate_config_values(config: Config) -> list[str]:
    errors = []

    # duration and workload
    if config.start.duration_time_s <= 0:
        errors.append("duration must be > 0")
    if config.workload.request_per_minute <= 0:
        errors.append("request per minute must be > 0")
    total_requests = (config.start.duration_time_s / 60) * config.workload.request_per_minute
    if total_requests < 1:
        errors.append(f"config would generate 0 requests")

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
    if config.question.context_window <= 0:
        errors.append("context_window must be > 0")

    # latency
    if config.latency.max_ms <= 0:
        errors.append("latency must be > 0")
    if config.latency.latency_window_s <= 0:
        errors.append("latency must be > 0")

    # start time format
    try:
        datetime.strptime(config.start.start_time_simulated, "%d/%m/%Y")
    except ValueError:
        errors.append(f"start time invalid format, expected DD/MM/YYYY")

    return errors


def validate_cluster_reachability(config: Config) -> list[str]:
    """Check all cluster control planes are reachable."""
    errors = []

    for cluster in config.clusters:
        try:
            response = requests.get(
                f"http://{cluster.ip}:{cluster.port}/get_cluster_information",
                timeout=10,
            )
            response.raise_for_status()
            log.info("validate.cluster_reachable", cluster=cluster.name)
        except Exception as e:
            errors.append(f"cluster {cluster.name} unreachable: {str(e)}")
            log.warning("validate.cluster_unreachable", cluster=cluster.name, error=str(e))

    return errors

def validate_electricity_maps(config: Config) -> list[str]:
    """Check electricity maps API has data for each cluster's zone."""
    errors = []

    # use simulated start time from config
    try:
        start = datetime.strptime(config.start.start_time_simulated, "%d/%m/%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return ["cannot validate APIs: invalid start_time_simulated format"]

    end = start + timedelta(seconds=config.start.duration_time_s)

    for cluster in config.clusters:
        zone = cluster.simulated_country_code

        try:
            carbon = fetch_carbon_intensity(start, end, zone)
            if not carbon:
                errors.append(f"cluster {cluster.name}: no carbon intensity data for zone={zone} at {start} to {end}")
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
    """Check Orin proxy has data for DK clusters at simulated time."""
    errors = []

    try:
        start = datetime.strptime(config.start.start_time_simulated, "%d/%m/%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return []

    end = start + timedelta(seconds=config.start.duration_time_s)

    for cluster in config.clusters:
        if not cluster.simulated_country_code.upper().startswith("DK"):
            continue
        try:
            data = get_dk_hourly(start, end)
            if not data:
                errors.append(f"cluster {cluster.name}: no DK energy data for {start} - is the Orin proxy running and does it have data for this time range?")
        except Exception as e:
            errors.append(f"cluster {cluster.name}: DK energy proxy unreachable: {str(e)}")

    return errors

def validate_pv_data(config: Config) -> list[str]:
    """Check PV CSV has data for each cluster's zone."""
    errors = []

    try:
        start = datetime.strptime(config.start.start_time_simulated, "%d/%m/%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return []

    end = start + timedelta(seconds=config.start.duration_time_s)
    pv_capacity_w = EnergyConfig().pv_capacity_w
    for cluster in config.clusters:
        try:
            data = get_power(start, end, cluster.simulated_country_code, pv_capacity_w=pv_capacity_w)
            if not data:
                errors.append(f"cluster {cluster.name}: no PV data for zone={cluster.simulated_country_code} at {start} to {end}")
        except Exception as e:
            errors.append(f"cluster {cluster.name}: PV data error: {str(e)}")

    return errors

def validate_config(config: Config) -> dict:
    """Run all validations and return result."""
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