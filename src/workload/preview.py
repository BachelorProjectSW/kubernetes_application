from collections import Counter
from generator import generate_workload


def preview(timestamps):
    total_requests = len(timestamps)
    print(f"Total requests: {total_requests}\n")

    if total_requests == 0:
        print("No events generated. Increase duration or RPM.")
        return
    
    print("First 10 events:")
    for ts in timestamps[:10]:
        print(f"{ts:.2f}s")
    
    print("\nLast 10 events:")
    for ts in timestamps[-10:]:
        print(f"{ts:.2f}s")

    # Optional: simple histogram of requests per second
    buckets = Counter(int(t) for t in timestamps)
    print("\nRequests per second:")
    for sec in range(max(buckets) + 1):
        print(f"{sec:3d}s: {'#' * buckets[sec]}")


if __name__ == "__main__":
    timestamps = generate_workload(
        duration_s=60,
        rpm=2000,
        pattern="peaks",
        seed=42,
        peakiness=1,
    )
    preview(timestamps)
