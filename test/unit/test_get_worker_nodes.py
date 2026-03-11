import pytest
from unittest.mock import patch
from cluster_api.services.get_worker_nodes import get_worker_nodes
from kubernetes.client import V1NodeList, V1Node, V1ObjectMeta, V1NodeStatus, V1NodeCondition


def get_fake_v1_node_list():
    """Return a very simple V1NodeList."""
    worker_node = V1Node(
        metadata=V1ObjectMeta(name="worker-1", labels={}),
        status=V1NodeStatus(conditions=[V1NodeCondition(type="Ready", status="True")])
    )
    control_plane_node = V1Node(
        metadata=V1ObjectMeta(name="master-1",
            labels={"node-role.kubernetes.io/control-plane": "true"}),
        status=V1NodeStatus(conditions=[V1NodeCondition(type="Ready", status="True")])
    )
    return V1NodeList(items=[worker_node, control_plane_node])


@pytest.mark.unit
def test_get_worker_nodes():
    """Test with a mocked V1NodeList."""
    fake_nodes = get_fake_v1_node_list()

    # Patch in the module where get_worker_nodes actually imported get_api_client
    with patch("cluster_api.services.get_worker_nodes.get_api_client") as mock_client:
        mock_api = mock_client.return_value
        mock_api.list_node.return_value = fake_nodes

        result = get_worker_nodes()

    assert [{"name": "worker-1"}] == result
