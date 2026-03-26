import random
import math


def generate_workload(duration_s, rpm, pattern="steady", seed=42, peakiness=0.5):
    random.seed(seed)

    if rpm <= 0 or duration_s <= 0:
        return []

    total_requests = int(duration_s * rpm / 60)
    if total_requests <= 0:
        return []

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

        # --- allocate requests by weighted sampling so low-RPM workloads
        # still keep the exact request count ---
        second_choices = random.choices(
            population=range(duration_s),
            weights=intensity,
            k=total_requests,
        )

        for sec in second_choices:
            ts = sec + random.uniform(0, 1)
            timestamps.append(ts)

    timestamps.sort()
    return timestamps
