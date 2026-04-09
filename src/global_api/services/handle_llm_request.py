import time
import uuid
import requests
from datetime import datetime, timezone

from ...models.basemodels import QuestionConfig
from .cluster_data import get_cluster_runtime_data
from .scoring import choose_cluster, compute_grid_fraction, compute_carbon_blend, compute_cost_blend
from ..util.all_configuration import config_store
from ...custom_logging.logger import log_request


def handle_llm_request(question: QuestionConfig):
    """Send the question to the local cluster request scheduler llama-service."""
    request_id = str(uuid.uuid4())
    config = config_store.get()

    # TODO: compute actual simulated time from (datetime.now() - start_time_real + start_time_simulated)
    simulated_time = datetime.now(timezone.utc)

    all_cluster_energy_data = [
        get_cluster_runtime_data(cluster, simulated_time, config.energy)
        for cluster in config.clusters
    ]

    cluster, cluster_energy_data = choose_cluster(
        config.clusters, all_cluster_energy_data, config.weights, config.energy
    )

    renewable_fraction = compute_grid_fraction(
        cluster_energy_data.renewable_output_w, cluster_energy_data.cluster_load_w
    )
    blended_carbon = compute_carbon_blend(
        cluster_energy_data.renewable_output_w,
        cluster_energy_data.cluster_load_w,
        cluster_energy_data.grid_carbon_intensity,
    )
    blended_cost = compute_cost_blend(
        cluster_energy_data.renewable_output_w,
        cluster_energy_data.cluster_load_w,
        cluster_energy_data.grid_electricity_price,
    )

    url = f"http://{cluster.ip}:{cluster.port}/handle_llm_request"

    t_start = time.monotonic()
    response = requests.post(url, json=question.model_dump())
    latency_ms = (time.monotonic() - t_start) * 1000

    result = response.json()

    log_request(
        request_id=request_id,
        cluster=cluster,
        node=None,  # TODO: resolve WorkerNode from response once cluster_api returns node name
        latency_ms=latency_ms,
        cluster_load_w=cluster_energy_data.cluster_load_w,
        renewable_fraction=renewable_fraction,
        blended_carbon_gco2_per_kwh=blended_carbon,
        blended_cost_eur_per_kwh=blended_cost,
    )

    return result
