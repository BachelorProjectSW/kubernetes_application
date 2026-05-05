import time

import requests
import structlog
from fastapi import HTTPException

from ...custom_logging.logger import log_request
from ...models.basemodels import LLMResponse, QuestionConfig
from ..util.all_configuration import config_store
from ..util.time_utils import compute_simulated_now
from .cluster_data import get_cluster_runtime_data
from .scoring import choose_cluster, compute_carbon_blend, compute_cost_blend, compute_grid_fraction


log = structlog.get_logger()


def handle_llm_request(question: QuestionConfig, trace_id: str):
    """Send the question to the local cluster request scheduler llama-service."""
    try:
        total_start = time.monotonic()
        config = config_store.get()

        simulated_time = compute_simulated_now(
            config.start.start_time_simulated,
            config.start.start_time_real,
        )

        all_cluster_energy_data = [
            get_cluster_runtime_data(
                cluster,
                simulated_time,
                config.energy,
                config.latency.latency_window_s,
                config.id,
            )
            for cluster in config.clusters
        ]

        cluster, cluster_energy_data = choose_cluster(
            config.clusters,
            all_cluster_energy_data,
            config.weights,
            config.energy,
            config.latency.max_ms,
        )
        choose_cluster_end = int((time.monotonic() - total_start) * 1000)

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

        headers = {"X-Trace-Id": trace_id}

        try:
            response = requests.post(
                url,
                json=question.model_dump(),
                headers=headers,
                timeout=1000,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            global_total_time_ms = int((time.monotonic() - total_start) * 1000)
            log_request(
                cluster_name=cluster.name,
                worker_node_name="unknown",
                success=False,
                latency_ms=global_total_time_ms,
                cluster_load_w=cluster_energy_data.cluster_load_w,
                renewable_fraction=renewable_fraction,
                blended_carbon_gco2_per_kwh=blended_carbon,
                blended_cost_eur_per_kwh=blended_cost,
                question=question.question,
                answer=None,
                response_status_code=500,
                all_content=data,
                trace_id=trace_id,
                global_choose_cluster=choose_cluster_end,
                global_total_time_ms=global_total_time_ms,
            )
            raise Exception(e)

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
        log.debug("global_api.llm_content", llm_content=llm_content, worker_node=worker_node)
        answer = None

        if isinstance(llm_content, dict):
            answer = llm_content.get("content") or None

        global_total_time_ms = int((time.monotonic() - total_start) * 1000)

        log_request(
            cluster_name=cluster.name,
            worker_node_name=worker_node.name,
            success=True,
            latency_ms=global_total_time_ms,
            cluster_load_w=cluster_energy_data.cluster_load_w,
            renewable_fraction=renewable_fraction,
            blended_carbon_gco2_per_kwh=blended_carbon,
            blended_cost_eur_per_kwh=blended_cost,
            question=question.question,
            answer=answer,
            response_status_code=result.llama_response_status_code,
            all_content=llm_content,
            trace_id=trace_id,
            global_choose_cluster=choose_cluster_end,
            global_total_time_ms=global_total_time_ms,
            cluster_queue_time_ms=result.cluster_queue_time_ms,
            cluster_llama_inference_ms=result.cluster_llama_inference_ms,
        )

        return result
    except Exception as e:
        log_request(
            cluster_name=cluster.name if "cluster" in locals() else "unknown",
            worker_node_name=(
                worker_node.name
                if "worker_node" in locals() and worker_node is not None
                else "unknown"
            ),
            success=False,
            latency_ms=(
                global_total_time_ms
                if "global_total_time_ms" in locals()
                else 0
            ),
            cluster_load_w=(
                cluster_energy_data.cluster_load_w
                if "cluster_energy_data" in locals()
                else 0
            ),
            renewable_fraction=(
                renewable_fraction
                if "renewable_fraction" in locals()
                else 0
            ),
            blended_carbon_gco2_per_kwh=(
                blended_carbon
                if "blended_carbon" in locals()
                else 0
            ),
            blended_cost_eur_per_kwh=(
                blended_cost
                if "blended_cost" in locals()
                else 0
            ),
            question=question.question,
            answer=answer if "answer" in locals() else None,
            response_status_code=(
                result.llama_response_status_code
                if "result" in locals()
                else 500
            ),
            all_content=(
                llm_content
                if "llm_content" in locals()
                else None
            ),
            trace_id=trace_id,
            global_choose_cluster=(
                choose_cluster_end
                if "choose_cluster_end" in locals()
                else 0
            ),
            global_total_time_ms=(
                global_total_time_ms
                if "global_total_time_ms" in locals()
                else 0
            ),
            cluster_queue_time_ms=(
                result.cluster_queue_time_ms
                if "result" in locals()
                else None
            ),
            cluster_llama_inference_ms=(
                result.cluster_llama_inference_ms
                if "result" in locals()
                else None
            ),
        )
        raise HTTPException(status_code=500, detail=str(e))
