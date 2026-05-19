import pytest

from src.global_api.services.scoring import choose_cluster
from test.k3d.cluster_configs.test_config import get_test_config
from test.k3d.cluster_configs.worker_nodes import UnitTestClusterRuntimeData

@pytest.mark.unit
def test_picks_the_greener_cluster_when_other_factors_are_equal():
    """With equal latency, the fully-renewable cluster outscores the grid one."""
    config = get_test_config()
    clusters = config.clusters
    runtime = [
        UnitTestClusterRuntimeData.green(),
        UnitTestClusterRuntimeData.dirty(),
    ]

    chosen, chosen_data = choose_cluster(
        clusters, runtime, config.weights, config.energy, config.latency.max_ms
    )

    assert chosen.name == clusters[0].name
    assert chosen_data is runtime[0]

@pytest.mark.unit
def test_skips_clusters_with_all_nodes_powered_off():
    """A powered-off cluster is excluded even if its energy would score best."""
    config = get_test_config()
    clusters = config.clusters
    # The green cluster would win, but it is powered off and must be skipped.
    runtime = [
        UnitTestClusterRuntimeData.make(
            renewable_output_w=2000.0, cluster_load_w=1000.0, all_nodes_powered_off=True
        ),
        UnitTestClusterRuntimeData.dirty(),
    ]

    chosen, chosen_data = choose_cluster(
        clusters, runtime, config.weights, config.energy, config.latency.max_ms
    )

    assert chosen.name == clusters[1].name
    assert chosen_data is runtime[1]

@pytest.mark.unit
def test_lower_latency_cluster_wins_under_latency_weight():
    """When energy is identical, the cluster with lower latency scores higher."""
    config = get_test_config()
    config.weights.gco2 = 0.0
    config.weights.cost = 0.0
    config.weights.latency = 1.0
    clusters = config.clusters
    runtime = [
        UnitTestClusterRuntimeData.make(avg_latency_ms=8000.0),
        UnitTestClusterRuntimeData.make(avg_latency_ms=500.0),
    ]

    chosen, _ = choose_cluster(
        clusters, runtime, config.weights, config.energy, config.latency.max_ms
    )

    assert chosen.name == clusters[1].name

@pytest.mark.unit
def test_single_cluster_is_returned_directly():
    """A single eligible cluster is returned with its own runtime data."""
    config = get_test_config()
    clusters = config.clusters[:1]
    runtime = [UnitTestClusterRuntimeData.dirty()]

    chosen, chosen_data = choose_cluster(
        clusters, runtime, config.weights, config.energy, config.latency.max_ms
    )

    assert chosen.name == clusters[0].name
    assert chosen_data is runtime[0]
