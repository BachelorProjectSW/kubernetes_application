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
        #The interval between the requests
        interval = 60 / rpm
        #So foreach request we do generate the interval at which it should be sent at
        #The random.uniform gives us a number between 0 and 1 such that we dont just send it exactly at 2
        #seconds but rather at 2+0.22= 2.22 seconds fx.
        for i in range(total_requests):
            timestamps.append(i * interval + random.uniform(0, 1))

    elif pattern == "peaks":
        intensity = []

        # Generate multiple waves
        waves = []
        num_waves = 3 + int(peakiness * 3)
        
        # _ = we do not use the number 
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

        #basically add the little jitter to the thing type of vibe
        for sec in second_choices:
            ts = sec + random.uniform(0, 1)
            timestamps.append(ts)
    
    #Then we sort them, because the jitter could have messed up the order
    timestamps.sort()
    return timestamps
