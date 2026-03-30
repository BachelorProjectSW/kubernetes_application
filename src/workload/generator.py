import random
import math


def generate_workload(duration_s, rpm, pattern="steady", seed=42, peakiness=0.5):
    """Generate request timestamps over a given duration.

    This function simulates incoming request timestamps based on a specified
    workload pattern. It supports steady traffic as well peaks
    generated from sine waves.

    Args:
        duration_s (int): Total duration of the workload in seconds.
        rpm (float): Target requests per minute.
        pattern (str, optional): Traffic pattern to generate. Supported values:
            - "steady": Evenly spaced requests with slight randomness.
            - "peaks": Bursty traffic based on overlapping sine waves.
            Defaults to "steady".
        seed (int, optional): Random seed for reproducibility. Defaults to 42.
        peakiness (float, optional): Controls the variability and number of peaks
            in the "peaks" pattern. Higher values produce more intense and complex
            bursts. Defaults to 0.5.

    Returns:
        list[float]: Sorted list of request timestamps (in seconds).

    """
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
            timestamps.append(i * interval + random.uniform(0, 1))

    elif pattern == "peaks":
        intensity = []

        # Generate multiple waves
        waves = []
        num_waves = 3 + int(peakiness * 3)

        for _ in range(num_waves):
            wave_length = random.uniform(duration_s * 0.1, duration_s * 0.8)
            frequency = 2 * math.pi / wave_length
            phase = random.uniform(0, 2 * math.pi)
            amplitude = random.uniform(0.2, 1.0) * peakiness

            waves.append((frequency, phase, amplitude))

        # Build intensity curve
        for t in range(duration_s):
            value = 1.0  # baseline

            for freq, phase, amp in waves:
                value += amp * math.sin(t * freq + phase)

            intensity.append(max(value, 0.1))

        # Allocate requests by weighted sampling so low-RPM workloads
        # Still keep the exact request count
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
