from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.global_api.services.cluster_data import get_cluster_runtime_data
from src.models.basemodels import ClusterConfig, EnergyConfig
from test.k3d.cluster_configs.test_config import get_test_config


def _make_cluster(simulated_country_code: str) -> ClusterConfig:
    """Create a minimal cluster config for runtime data tests."""
    base_cluster = get_test_config().clusters[0]
    return base_cluster.model_copy(
        update={
            "name": simulated_country_code.lower(),
            "simulated_country_code": simulated_country_code,
        }
    )


def _mock_worker_nodes(*statuses: str):
    return [
        {
            "name": f"node-{index}",
            "ip": "127.0.0.1",
            "status": status,
            "gpio": index + 1,
        }
        for index, status in enumerate(statuses)
    ]


@pytest.mark.unit
def test_runtime_data_adds_orin_base_load_for_denmark_cluster():
    """Denmark clusters include Orin base load in the total cluster load."""
    cluster = _make_cluster("DK-DK1")

    with (
        patch("src.global_api.services.cluster_data.market_data_store.get_power", return_value=[]),
        patch("src.global_api.services.cluster_data.market_data_store.get_carbon", return_value=[]),
        patch("src.global_api.services.cluster_data.market_data_store.get_price", return_value=[]),
        patch("src.global_api.services.cluster_data.compute_cluster_load", return_value=1000.0),
        patch("src.global_api.services.cluster_data.get_avg_latency_for_cluster", return_value=0.0),
        patch(
            "src.global_api.services.cluster_data.get_dk_hourly",
            return_value=[{"consumption_w": 250.0}],
        ) as mock_dk,
        patch("src.global_api.services.cluster_data.requests.get") as mock_requests_get,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_worker_nodes("working", "idle", "off")
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        result = get_cluster_runtime_data(
            cluster,
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            EnergyConfig(),
            latency_window_s=300,
            config_id="123",
        )

    assert result.cluster_load_w == 1250.0
    mock_dk.assert_called_once()


@pytest.mark.unit
def test_runtime_data_keeps_cluster_load_for_non_denmark_cluster():
    """Non-Denmark clusters should not fetch Orin base load."""
    cluster = _make_cluster("PT")

    with (
        patch("src.global_api.services.cluster_data.market_data_store.get_power", return_value=[]),
        patch("src.global_api.services.cluster_data.market_data_store.get_carbon", return_value=[]),
        patch("src.global_api.services.cluster_data.market_data_store.get_price", return_value=[]),
        patch("src.global_api.services.cluster_data.compute_cluster_load", return_value=1000.0),
        patch("src.global_api.services.cluster_data.get_avg_latency_for_cluster", return_value=0.0),
        patch("src.global_api.services.cluster_data.get_dk_hourly") as mock_dk,
        patch("src.global_api.services.cluster_data.requests.get") as mock_requests_get,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = _mock_worker_nodes("working", "idle")
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        result = get_cluster_runtime_data(
            cluster,
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            EnergyConfig(),
            latency_window_s=300,
            config_id="123",
        )

    assert result.cluster_load_w == 1000.0
    mock_dk.assert_not_called()
