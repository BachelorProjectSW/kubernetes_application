from collections import Counter
from generator import generate_workload


def preview(timestamps):
    buckets = Counter(int(t) for t in timestamps)
    for sec in range(max(buckets) + 1):
        print(f"{sec}: {'#' * buckets[sec]}")
    
    total_requests = len(timestamps)
    print(f"Total requests: {total_requests}\n")



if __name__ == "__main__":
    timestamps = generate_workload(
        duration_s=1000,
        rpm=1000,
        pattern="peaks",
        seed=43,
        peakiness=10,
    )
    preview(timestamps)
