import time
from ...models.basemodels import Config, ClusterInformation
from ...models.enum import WorkerStatus
from scoring import score_cluster
from ..util.all_configuration import config_store
import math
import requests

#TODO this should be in util and return worker nodes logs for each cluster.
def get_worker_nodes_logs():
    """Pass."""
    pass


#TODO this should be in util and return latency logs for each request.
def get_avg_latency(time_interval: int, ):
    """Return avg latency from now and {time_interval} seconds ago."""
    pass


def get_avg_latency_per_node_ms():
    """Analise logs."""
    #TODO analyse logs
    return 10000


def get_current_active_nodes(clusters: list[ClusterInformation]):
    """Analise logs."""
    active_nodes_counter = 0
    for cluster in clusters:
        for worker_node in cluster.worker_nodes:
            status = worker_node.status
            if status == WorkerStatus.WORKING or status == WorkerStatus.IDLE:
                active_nodes_counter+= 1

    return active_nodes_counter


def get_current_rps():
    """Analyse logs."""
    #TODO analyse logs
    return 1

def estimate_nodes_to_add(
    avg_latency_per_node_ms: float,
    max_latency_ms: float,
    current_active_nodes: int,
    current_rps: float,
) -> int:
    """
    Estimate how many more worker nodes are needed
    to keep latency under max_latency_s.
    """
    # how many nodes needed in total
    required_nodes = math.ceil((avg_latency_per_node_ms * current_rps) / max_latency_ms)
    
    # how many more to add
    nodes_to_add = max(0, required_nodes - current_active_nodes)
    
    return nodes_to_add


def turn_nodes_on(config: Config):
    """Turn nodes on."""
    
    # Sort clusters by score (highest first)
    sorted_clusters = sorted(
        clusters,
        key=lambda cluster: score_cluster(
            cluster.renewable_output_w,
            cluster.cluster_load_w,
            cluster.grid_carbon_intensity,
            cluster.grid_electricity_price,
            config.weights.gco2,
            config.weights.cost,
            config.energy,
        ),
        reverse=True,  # highest first
    )

    avg_latency_per_node_ms = get_avg_latency_per_node_ms()
    max_latency_ms = config.latency.max_ms
    current_active_nodes = get_current_active_nodes(clusters)
    current_rps = get_current_rps()
    
    nodes_to_add = estimate_nodes_to_add(avg_latency_per_node_ms,max_latency_ms, current_active_nodes, current_rps)
    for cluster in sorted_clusters:
        if nodes_to_add <= 0:
            break
        powered_off_nodes = 0
        for worker_node in cluster.worker_nodes:
            if worker_node.status == WorkerStatus.OFF:
                powered_off_nodes += 1

        amount = min(nodes_to_add, powered_off_nodes)
        
        url = f"http://{cluster.ip}:{cluster.port}/turn_on_nodes/"
        response = requests.post(url, json={"number_of_nodes": amount}, timeout=10)
        turned_on = response.json().get("turned_on", amount)
        
        nodes_to_add -= turned_on



def turn_off_idle_nodes(idle_time_s: int):
    """Turn nodes off."""
    print(idle_time_s)
    #TODO Turn of alle nodes which has been idle in more than idle_time_s secunds. 
    #TODO Do it by send a request to each cluster to check for idle time. 


async def power_scheduler_loop():
    """Check every x seconds whether more working nodes should be turn on or off."""
    config = config_store.get() 
    timeout = config.power_scheduler.timeout_s
    idle_time_for_turn_off_s = config.power_scheduler.idle_time_for_turn_off_s
    while config.power_scheduler.start:
        time.sleep(timeout)
        turn_nodes_on(config)
        turn_off_idle_nodes(idle_time_for_turn_off_s)
