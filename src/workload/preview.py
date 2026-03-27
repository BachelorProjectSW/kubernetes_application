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
        duration_s=2000,
        rpm=2000,
        pattern="steady",
        seed=43,
        peakiness=0.1,
    )
    preview(timestamps)
