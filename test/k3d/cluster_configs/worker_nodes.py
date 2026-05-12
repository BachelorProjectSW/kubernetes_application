from src.models.basemodels import ClusterInformation, QuestionConfig, WorkerNode
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
