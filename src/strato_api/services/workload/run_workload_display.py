import random
import math
import matplotlib.pyplot as plt


def generate_workload_charts(duration_s, rpm, pattern="steady", seed=42, peakiness=0.5):
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






    plt.rcParams.update({
        "font.size": 16,          # Base font size
        "axes.titlesize": 20,     # Figure title
        "axes.labelsize": 18,     # X/Y labels
        "xtick.labelsize": 14,    # X tick labels
        "ytick.labelsize": 14,    # Y tick labels
        "legend.fontsize": 14,    # Legend text
    })
    # ----------------------superposition----------------

    plt.figure(figsize=(12, 5))
    t = list(range(duration_s))

    for i, (freq, phase, amp) in enumerate(waves):
        wave_values = [
            amp * math.sin(x * freq + phase)
            for x in t
        ]

        plt.plot(t, wave_values, alpha=0.4, label=f"Wave {i}")

    plt.plot(t, intensity, linewidth=3, label="Combined intensity")

    plt.xlabel("Time (s)")
    plt.ylabel("Intensity")
    plt.title("Superposition of sine waves")
    plt.legend()

    plt.tight_layout()
    plt.show()

    # -------------------------------------------probability-------------------------------------
    sum_intensity = sum(intensity)
    probability = [
        value / sum_intensity
        for value in intensity
    ]
    plt.figure(figsize=(12, 4))

    plt.plot(t, probability)

    plt.fill_between(t, probability, alpha=0.3)

    plt.xlabel("Time (s)")
    plt.ylabel("Probability")
    plt.title("Normalized probability distribution")

    plt.tight_layout()
    plt.show()


#     # --------------- histogram --------------

    plt.figure(figsize=(12, 4))

    plt.hist(timestamps, bins=30)

    plt.xlabel("Time (s)")
    plt.ylabel("Requests")
    plt.title("Request density over time")

    plt.tight_layout()
    plt.show()


generate_workload_charts(
    duration_s=1200,
    rpm=8,
    pattern="peaks",
    seed=15,
    peakiness=0.2,
)