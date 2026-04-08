from collections import Counter
from strato_api.services.workload.generator import generate_workload


def preview(timestamps):
    """Sort each timestamps into seconds and print it for debug."""
    buckets = Counter(int(t) for t in timestamps)
    for sec in range(max(buckets) + 1):
        print(f"{sec}: {'#' * buckets[sec]}")

    total_requests = len(timestamps)
    print(f"Total requests: {total_requests}\n")


if __name__ == "__main__":
    import random
    timestamps = generate_workload(
        duration_s=1000,
        rpm=200,
        pattern="peaks",
        seed=random.uniform(0, 10000),
        peakiness=2.0,
    )
    preview(timestamps)
