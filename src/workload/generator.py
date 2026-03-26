import random
import math

def generate_workload(duration_s, rpm, pattern="steady", seed=42, peakiness=0.5):
    random.seed(seed)
    total_requests = int(duration_s * rpm / 60)
    timestamps = []

    if pattern == "steady":
        interval = 60 / rpm
        for i in range(total_requests):
            jitter = random.uniform(-0.05, 0.05) * interval
            timestamps.append(i * interval + jitter)

    elif pattern == "peaks":
        intensity = []

        # --- generate multiple waves with random properties ---
        waves = []
        num_waves = 3 + int(peakiness * 3)  # more peakiness = more complexity

        for _ in range(num_waves):
            wave_length = random.uniform(duration_s * 0.1, duration_s * 0.8)
            frequency = 2 * math.pi / wave_length
            phase = random.uniform(0, 2 * math.pi)
            amplitude = random.uniform(0.2, 1.0) * peakiness

            waves.append((frequency, phase, amplitude))

        # --- build intensity curve ---
        for t in range(duration_s):
            value = 1.0  # baseline

            for freq, phase, amp in waves:
                value += amp * math.sin(t * freq + phase)

            # add small randomness
            value += random.uniform(-0.1, 0.1)

            # clamp
            value = max(0.05, value)
            intensity.append(value)

        # --- normalize ---
        total_intensity = sum(intensity)
        requests_per_second = [
            (val / total_intensity) * total_requests
            for val in intensity
        ]

        # --- generate timestamps ---
        for sec, req_count in enumerate(requests_per_second):
            for _ in range(int(req_count)):
                ts = sec + random.uniform(0, 1)
                timestamps.append(ts)

    timestamps.sort()
    return timestamps
