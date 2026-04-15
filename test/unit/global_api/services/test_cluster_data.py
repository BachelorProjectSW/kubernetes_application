from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.global_api.services.cluster_data import get_cluster_runtime_data
from src.models.basemodels import ClusterConfig, EnergyConfig


def _make_cluster(simulated_country_code: str) -> ClusterConfig:
    """Create a minimal cluster config for runtime data tests."""
    return ClusterConfig(
        name=simulated_country_code.lower(),
        ip="127.0.0.1",
        port="8080",
        gpio_list=[1],
        simulated_country_code=simulated_country_code,
        llama_service_port="11434",
    )


@pytest.mark.unit
def test_runtime_data_adds_orin_base_load_for_denmark_cluster():
    """Denmark clusters include Orin base load in the total cluster load."""
    cluster = _make_cluster("DK-DK1")

    with (
        patch("src.global_api.services.cluster_data.get_power", return_value=[]),
        patch("src.global_api.services.cluster_data.fetch_carbon_intensity", return_value=[]),
        patch("src.global_api.services.cluster_data.fetch_price_data", return_value=[]),
        patch("src.global_api.services.cluster_data.compute_cluster_load", return_value=1000.0),
        patch(
            "src.global_api.services.cluster_data.get_dk_hourly",
            return_value=[{"consumption_w": 250.0}],
        ) as mock_dk,
    ):
        result = get_cluster_runtime_data(
            cluster,
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            EnergyConfig(),
        )

    assert result.cluster_load_w == 1250.0
    mock_dk.assert_called_once()


@pytest.mark.unit
def test_runtime_data_keeps_cluster_load_for_non_denmark_cluster():
    """Non-Denmark clusters should not fetch Orin base load."""
    cluster = _make_cluster("PT")

    with (
        patch("src.global_api.services.cluster_data.get_power", return_value=[]),
        patch("src.global_api.services.cluster_data.fetch_carbon_intensity", return_value=[]),
        patch("src.global_api.services.cluster_data.fetch_price_data", return_value=[]),
        patch("src.global_api.services.cluster_data.compute_cluster_load", return_value=1000.0),
        patch("src.global_api.services.cluster_data.get_dk_hourly") as mock_dk,
    ):
        result = get_cluster_runtime_data(
            cluster,
            datetime(2025, 1, 1, tzinfo=timezone.utc),
            EnergyConfig(),
        )

    assert result.cluster_load_w == 1000.0
    mock_dk.assert_not_called()
