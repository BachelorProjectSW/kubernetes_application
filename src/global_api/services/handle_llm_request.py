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
from ..util.time_utils import compute_simulated_now


log = structlog.get_logger()


# TODO jeg tror ikke den tager højde for at den ikke
# sender request ud til at cluster med kun slukkede worker nodes.
# TODO Så derfor sikre sig at der er nogle tændte og hvis ikke så tænd nogle inden:D
def handle_llm_request(question: QuestionConfig, trace_id: str | None = None):
    """Send the question to the local cluster request scheduler llama-service."""
    request_id = str(uuid.uuid4())
    trace_id = trace_id
    config = config_store.get()
    if config is None:
        raise HTTPException(status_code=409,
                            detail="No active config. Start a test before sending questions.")
    if not config.clusters:
        raise HTTPException(status_code=409,
                            detail="No clusters configured in active config.")

    total_start = time.monotonic()

    log.info(
        "global_api.llm.request_started",
        service="global_api",
        trace_id=trace_id,
        request_id=request_id,
        cluster_count=len(config.clusters),
    )

    try:
        simulated_time = compute_simulated_now(
            config.start.start_time_simulated,
            config.start.start_time_real,
        )
    except Exception as e:
        simulated_time = datetime.now(timezone.utc)
        log.warning(
            "global_api.llm.simulated_time_fallback_to_now",
            trace_id=trace_id,
            request_id=request_id,
            error=str(e),
        )

    market_data_fetch_start = time.monotonic()

    all_cluster_energy_data = [
        get_cluster_runtime_data(
            cluster,
            simulated_time,
            config.energy,
            config.latency.latency_window_s,
        )
        for cluster in config.clusters
    ]

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

    headers = {}
    if trace_id:
        headers["X-Trace-Id"] = trace_id

    try:
        response = requests.post(
            url,
            json=question.model_dump(),
            headers=headers,
            timeout=1000,
        )
        response.raise_for_status()
        data = response.json()
    except requests.HTTPError as e:
        global_cluster_api_call_ms = int((time.monotonic() - t_start) * 1000)
        global_total_time_ms = int((time.monotonic() - total_start) * 1000)
        response_status_code = e.response.status_code if e.response else 502
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
            response_status_code=response_status_code,
            all_content=e.response.text if e.response is not None else str(e),
            trace_id=trace_id,
            global_market_data_fetch_ms=global_market_data_fetch_ms,
            global_cluster_scoring_ms=global_cluster_scoring_ms,
            global_cluster_api_call_ms=global_cluster_api_call_ms,
            global_total_time_ms=global_total_time_ms,
        )
        detail = f"Cluster API returned {e.response.status_code if e.response else 'error'}"
        raise HTTPException(status_code=502, detail=detail) from e
    except requests.RequestException as e:
        global_cluster_api_call_ms = int((time.monotonic() - t_start) * 1000)
        global_total_time_ms = int((time.monotonic() - total_start) * 1000)
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
            response_status_code=502,
            all_content=str(e),
            trace_id=trace_id,
            global_market_data_fetch_ms=global_market_data_fetch_ms,
            global_cluster_scoring_ms=global_cluster_scoring_ms,
            global_cluster_api_call_ms=global_cluster_api_call_ms,
            global_total_time_ms=global_total_time_ms,
        )
        raise HTTPException(status_code=502, detail=f"Cluster API request failed: {str(e)}") from e
    except ValueError as e:
        global_cluster_api_call_ms = int((time.monotonic() - t_start) * 1000)
        global_total_time_ms = int((time.monotonic() - total_start) * 1000)
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
            response_status_code=502,
            all_content=str(e),
            trace_id=trace_id,
            global_market_data_fetch_ms=global_market_data_fetch_ms,
            global_cluster_scoring_ms=global_cluster_scoring_ms,
            global_cluster_api_call_ms=global_cluster_api_call_ms,
            global_total_time_ms=global_total_time_ms,
        )
        raise HTTPException(status_code=502, detail=f"Invalid JSON from cluster API: {str(e)}") from e

    global_cluster_api_call_ms = int((time.monotonic() - t_start) * 1000)
    global_total_time_ms = int((time.monotonic() - total_start) * 1000)

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
            response_status_code=502,
            all_content=data,
            trace_id=trace_id,
            global_market_data_fetch_ms=global_market_data_fetch_ms,
            global_cluster_scoring_ms=global_cluster_scoring_ms,
            global_cluster_api_call_ms=global_cluster_api_call_ms,
            global_total_time_ms=global_total_time_ms,
        )
        raise HTTPException(status_code=502, detail="Invalid cluster response payload")

    result = LLMResponse(
        llm_content=data["llm_content"],
        worker_node=data["worker_node"],
        inflight_requests_at_selection=data["inflight_requests_at_selection"],
        active_requests_at_selection=data["active_requests_at_selection"],
        queued_requests_at_selection=data["queued_requests_at_selection"],
        max_slots=data["max_slots"],
        cluster_queue_time_ms=data.get("cluster_queue_time_ms"),
        cluster_llama_inference_ms=data.get("cluster_llama_inference_ms"),
        llama_response_status_code=data.get("llama_response_status_code"),
    )
    worker_node = result.worker_node
    llm_content = result.llm_content
    log.debug("global_api.llm_content", llm_content=llm_content)
    answer = None

    if isinstance(llm_content, dict):
        answer = llm_content.get("content") or None

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
        response_status_code=result.llama_response_status_code,
        all_content=llm_content,
        trace_id=trace_id,
        global_market_data_fetch_ms=global_market_data_fetch_ms,
        global_cluster_scoring_ms=global_cluster_scoring_ms,
        global_cluster_api_call_ms=global_cluster_api_call_ms,
        global_total_time_ms=global_total_time_ms,
        cluster_queue_time_ms=result.cluster_queue_time_ms,
        cluster_llama_inference_ms=result.cluster_llama_inference_ms,
    )

    return result
