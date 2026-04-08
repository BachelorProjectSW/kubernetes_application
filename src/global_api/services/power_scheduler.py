import time
from ...models.basemodels import Config, ClusterInformation
from scoring import score_cluster
from ..util.all_configuration import config_store
import math

#TODO this should be in util and return worker nodes logs for each cluster.
def get_worker_nodes_logs():
    """Pass."""
    pass


#TODO this should be in util and return latency logs for each request.
def get_avg_latency(time_interval: int, ):
    """Return avg latency from now and {time_interval} seconds ago."""
    pass

def get_avg_latency_per_node_s():
    """Analise logs."""
    #TODO analyse logs
    return 17


def get_current_active_nodes(clusters: list[ClusterInformation]):
    """Analise logs."""
    active_nodes_counter = 0
    for cluster in clusters:
        for worker_node in cluster.worker_nodes:
            status = worker_node.status
            if status == 'working' or status == 'idle':
                

    return active_nodes_counter


def get_current_rps():
    """Analise logs."""
    #TODO analyse logs
    return 17

def estimate_nodes_to_add(
    avg_latency_per_node_s: float,
    max_latency_s: float,
    current_active_nodes: int,
    current_rps: float,
) -> int:
    """
    Estimate how many more worker nodes are needed
    to keep latency under max_latency_s.
    """
    # how many nodes needed in total
    required_nodes = math.ceil((avg_latency_per_node_s * current_rps) / max_latency_s)
    
    # how many more to add
    nodes_to_add = max(0, required_nodes - current_active_nodes)
    
    return nodes_to_add


def turn_nodes_on(config: Config, diff_ms: int):
    """Turn nodes on."""

    # Sort clusters by score (highest first)
    sorted_clusters = sorted(
        config.clusters,
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

    required_nodes = estimate_nodes_to_add(17,)
    for cluster in sorted_clusters:
        #TODO 
        pass


def turn_off_idle_nodes(idle_time_s: int):
    """Turn nodes off."""
    print(idle_time_s)
    #TODO turn of alle nodes which has been idle in more than idle_time_s secunds. 


async def power_scheduler_loop():
    """Check every x seconds whether more working nodes should be turn on or off."""
    config = config_store.get() 
    max_latency = config.latency.max_ms
    timeout = config.power_scheduler.timeout_s
    while config.power_scheduler.start:
        time.sleep(timeout)
        worker_nodes_logs = get_worker_nodes_logs() #Should be found

        latency_logs = None #Should be found
        
        avg_latency = get_avg_latency(timeout)
        
        # If no request send
        if avg_latency <= 0:
            continue
        
        # If latency is too big
        elif avg_latency > max_latency:
            diff = avg_latency - max_latency
            turn_nodes_on(config, diff)