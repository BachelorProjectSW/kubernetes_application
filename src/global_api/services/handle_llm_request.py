import time
import uuid
import requests
from datetime import datetime, timezone
import structlog
from fastapi import HTTPException
from ...models.basemodels import QuestionConfig, LLMResponse
from .cluster_data import get_cluster_runtime_data
from .scoring import choose_cluster, compute_grid_fraction, compute_carbon_blend, compute_cost_blend
from ..util.all_configuration import config_store
from ...custom_logging.logger import log_request


log = structlog.get_logger()


def handle_llm_request(question: QuestionConfig):
    """Send the question to the local cluster request scheduler llama-service."""
    request_id = str(uuid.uuid4())
    config = config_store.get()

    # TODO: compute actual simulated time from (datetime.now() - start_time_real + start_time_simulated)
    simulated_time = datetime.now(timezone.utc)

    all_cluster_energy_data = [
        get_cluster_runtime_data(cluster, simulated_time, config.energy, config.latency.latency_window_s)
        for cluster in config.clusters
    ]

    cluster, cluster_energy_data = choose_cluster(
        config.clusters, all_cluster_energy_data, config.weights, config.energy, config.latency.max_ms
    )

    grid_fraction = compute_grid_fraction(
        cluster_energy_data.renewable_output_w,
        cluster_energy_data.cluster_load_w,
    )
    renewable_fraction = round(max(0.0, 1.0 - grid_fraction), 4)
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
    data = response.json()

    if not isinstance(data, dict):
        log_request(
            request_id=request_id,
            cluster_name=cluster.name,
            worker_node_name="unknown",
            success=False,
            latency_ms=latency_ms,
            cluster_load_w=cluster_energy_data.cluster_load_w,
            renewable_fraction=renewable_fraction,
            blended_carbon_gco2_per_kwh=blended_carbon,
            blended_cost_eur_per_kwh=blended_cost,
            question=question.question,
            answer=None,
            all_content=data,
        )
        return HTTPException(status_code=500, detail=str(data))

    result = LLMResponse(
        llm_content=data["llm_content"],
        worker_node=data["worker_node"],
        inflight_requests_at_selection=data["inflight_requests_at_selection"],
        active_requests_at_selection=data["active_requests_at_selection"],
        queued_requests_at_selection=data["queued_requests_at_selection"],
        max_slots=data["max_slots"],
    )
    worker_node = result.worker_node
    llm_content = result.llm_content
    log.debug("global_api.llm_content", llm_content=llm_content)
    answer = None

    if isinstance(llm_content, dict):
        answer = (
            llm_content.get("content")
            or llm_content.get("response")
            or llm_content.get("text")
            or llm_content.get("completion")
        )
        if answer is not None:
            answer = str(answer)
    else:
        answer = str(llm_content)

    log_request(
        request_id=request_id,
        cluster_name=cluster.name,
        worker_node_name=worker_node.name,
        success=True,
        latency_ms=latency_ms,
        cluster_load_w=cluster_energy_data.cluster_load_w,
        renewable_fraction=renewable_fraction,
        blended_carbon_gco2_per_kwh=blended_carbon,
        blended_cost_eur_per_kwh=blended_cost,
        question=question.question,
        answer=answer,
        all_content=llm_content,
    )

    return llm_content
