import time
import uuid
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import structlog
from fastapi import HTTPException
from ...models.basemodels import QuestionConfig, LLMResponse
from .cluster_data import get_cluster_runtime_data
from .scoring import choose_cluster, compute_grid_fraction, compute_carbon_blend, compute_cost_blend
from ..util.all_configuration import config_store
from ...custom_logging.logger import log_request


log = structlog.get_logger()


def handle_llm_request(question: QuestionConfig, trace_id: str | None = None):
    """Send the question to the local cluster request scheduler llama-service."""
    request_id = str(uuid.uuid4())
    trace_id = trace_id or request_id
    config = config_store.get()
    total_start = time.monotonic()

    log.info(
        "global_api.llm.request_started",
        service="global_api",
        trace_id=trace_id,
        request_id=request_id,
        cluster_count=len(config.clusters),
    )

    # TODO: compute actual simulated time from (datetime.now() - start_time_real + start_time_simulated)
    simulated_time = datetime.now(timezone.utc)

    market_data_fetch_start = time.monotonic()

    all_cluster_energy_data: list = [None] * len(config.clusters)
    with ThreadPoolExecutor(max_workers=max(1, len(config.clusters))) as executor:
        futures = {
            executor.submit(
                get_cluster_runtime_data,
                cluster,
                simulated_time,
                config.energy,
                config.latency.latency_window_s,
            ): index
            for index, cluster in enumerate(config.clusters)
        }
        for future, index in ((f, i) for f, i in futures.items()):
            all_cluster_energy_data[index] = future.result()

    global_market_data_fetch_ms = int((time.monotonic() - market_data_fetch_start) * 1000)

    cluster_select_start = time.monotonic()
    cluster, cluster_energy_data = choose_cluster(
        config.clusters, all_cluster_energy_data, config.weights, config.energy, config.latency.max_ms
    )
    global_cluster_scoring_ms = int((time.monotonic() - cluster_select_start) * 1000)

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
    log.info(
        "global_api.llm.cluster_api_call_started",
        service="global_api",
        trace_id=trace_id,
        request_id=request_id,
        cluster_name=cluster.name,
        target_url=url,
        global_market_data_fetch_ms=global_market_data_fetch_ms,
        global_cluster_scoring_ms=global_cluster_scoring_ms,
    )

    response = requests.post(
        url,
        json=question.model_dump(),
        headers={"X-Trace-Id": trace_id},
    )
    global_cluster_api_call_ms = int((time.monotonic() - t_start) * 1000)
    global_total_time_ms = int((time.monotonic() - total_start) * 1000)
    data = response.json()

    if not isinstance(data, dict):
        log.warning(
            "global_api.llm.invalid_cluster_response",
            service="global_api",
            trace_id=trace_id,
            request_id=request_id,
            cluster_name=cluster.name,
            global_cluster_api_call_ms=int(global_cluster_api_call_ms),
            global_total_time_ms=global_total_time_ms,
            payload_type=type(data).__name__,
        )
        log_request(
            request_id=request_id,
            cluster_name=cluster.name,
            worker_node_name="unknown",
            success=False,
            latency_ms=global_cluster_api_call_ms,
            cluster_load_w=cluster_energy_data.cluster_load_w,
            renewable_fraction=renewable_fraction,
            blended_carbon_gco2_per_kwh=blended_carbon,
            blended_cost_eur_per_kwh=blended_cost,
            question=question.question,
            answer=None,
            all_content=data,
            trace_id=trace_id,
            global_market_data_fetch_ms=global_market_data_fetch_ms,
            global_cluster_scoring_ms=global_cluster_scoring_ms,
            global_cluster_api_call_ms=global_cluster_api_call_ms,
            global_total_time_ms=global_total_time_ms,
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

    log.info(
        "global_api.llm.request_completed",
        service="global_api",
        trace_id=trace_id,
        request_id=request_id,
        cluster_name=cluster.name,
        worker_node=worker_node.name,
        global_market_data_fetch_ms=global_market_data_fetch_ms,
        global_cluster_scoring_ms=global_cluster_scoring_ms,
        global_cluster_api_call_ms=global_cluster_api_call_ms,
        global_total_time_ms=global_total_time_ms,
    )

    log_request(
        request_id=request_id,
        cluster_name=cluster.name,
        worker_node_name=worker_node.name,
        success=True,
        latency_ms=global_cluster_api_call_ms,
        cluster_load_w=cluster_energy_data.cluster_load_w,
        renewable_fraction=renewable_fraction,
        blended_carbon_gco2_per_kwh=blended_carbon,
        blended_cost_eur_per_kwh=blended_cost,
        question=question.question,
        answer=answer,
        all_content=llm_content,
        trace_id=trace_id,
        global_market_data_fetch_ms=global_market_data_fetch_ms,
        global_cluster_scoring_ms=global_cluster_scoring_ms,
        global_cluster_api_call_ms=global_cluster_api_call_ms,
        global_total_time_ms=global_total_time_ms,
    )

    return result
