from src.models.basemodels import (
    ClusterInformation,
    ClusterRuntimeData,
    QuestionConfig,
    WorkerNode,
)
from src.models.enum import WorkerStatus

from .test_config import get_test_config


class UnitTestWorkerNodes:
    """Reusable worker-node fixtures for unit tests."""

    @staticmethod
    def make(
        name: str,
        status: WorkerStatus,
        gpio: int,
        ip: str = "127.0.0.1",
        inflight_requests: int = 0,
        max_slots: int = 0,
        forwarded_port: int | None = None,
    ) -> WorkerNode:
        """Create a worker node with sensible defaults for tests."""
        return WorkerNode(
            name=name,
            ip=ip,
            status=status,
            gpio=gpio,
            inflight_requests=inflight_requests,
            max_slots=max_slots,
            forwarded_port=forwarded_port,
        )

    @classmethod
    def from_specs(cls, specs: list[dict]) -> list[WorkerNode]:
        """Build a list of worker nodes from plain dictionaries."""
        return [cls.make(**spec) for spec in specs]

    @staticmethod
    def cluster_information(
        worker_nodes: list[WorkerNode],
        config_id: str = "test-config",
        cluster_name: str = "dk",
    ) -> ClusterInformation:
        """Create a cluster information object for unit tests."""
        base = get_test_config()
        cluster_config = next(cluster for cluster in base.clusters if cluster.name == cluster_name)
        return ClusterInformation(
            config_id=config_id,
            cluster_config=cluster_config.model_copy(
                update={
                    "name": cluster_name,
                    "ip": "127.0.0.1",
                    "port": "8080",
                    "simulated_country_code": "DK",
                }
            ),
            question_config=QuestionConfig(question="question", max_output_tokens=10),
            worker_nodes=worker_nodes,
        )

    @staticmethod
    def dk_workers() -> list[WorkerNode]:
        """Return a small default DK worker set used by multiple unit tests."""
        return [
            UnitTestWorkerNodes.make("n1", WorkerStatus.IDLE, 1, max_slots=1),
            UnitTestWorkerNodes.make("n2", WorkerStatus.OFF, 2, max_slots=0),
            UnitTestWorkerNodes.make("n3", WorkerStatus.OFF, 3, max_slots=0),
            UnitTestWorkerNodes.make("n4", WorkerStatus.OFF, 4, max_slots=0),
        ]

    @staticmethod
    def as_payload(worker_nodes: list[WorkerNode]) -> list[dict]:
        """Serialize worker nodes the way the cluster API returns them over HTTP.

        Use this so tests that exercise an HTTP boundary still source their
        node data from this fixture instead of hand-built dictionaries.
        """
        return [node.model_dump(mode="json") for node in worker_nodes]


class UnitTestClusterRuntimeData:
    """Reusable ClusterRuntimeData fixtures for global-scheduler unit tests."""

    @staticmethod
    def make(
        renewable_output_w: float = 0.0,
        cluster_load_w: float = 1000.0,
        grid_carbon_intensity: float = 300.0,
        grid_electricity_price: float = 0.20,
        avg_latency_ms: float = 1000.0,
        all_nodes_powered_off: bool = False,
    ) -> ClusterRuntimeData:
        """Create a runtime-data row with sensible defaults for tests."""
        return ClusterRuntimeData(
            renewable_output_w=renewable_output_w,
            cluster_load_w=cluster_load_w,
            grid_carbon_intensity=grid_carbon_intensity,
            grid_electricity_price=grid_electricity_price,
            avg_latency_ms=avg_latency_ms,
            all_nodes_powered_off=all_nodes_powered_off,
        )

    @classmethod
    def green(cls) -> ClusterRuntimeData:
        """Fully renewable cluster: zero blended carbon and cost (best score)."""
        return cls.make(renewable_output_w=2000.0, cluster_load_w=1000.0)

    @classmethod
    def dirty(cls) -> ClusterRuntimeData:
        """Grid-only cluster: full grid carbon and cost (worse score)."""
        return cls.make(renewable_output_w=0.0, cluster_load_w=1000.0)

    @classmethod
    def powered_off(cls) -> ClusterRuntimeData:
        """Return a cluster whose nodes are all off (skipped by scoring)."""
        return cls.make(all_nodes_powered_off=True)
