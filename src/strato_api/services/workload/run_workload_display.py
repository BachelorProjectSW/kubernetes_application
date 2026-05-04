import numpy as np
import matplotlib.pyplot as plt

duration_s = 300
t = np.linspace(0, duration_s, 3000)

wave1 = 0.8 * np.sin(0.03 * t)
wave2 = 0.5 * np.sin(0.09 * t + 1.4)
wave3 = 0.3 * np.sin(0.2 * t + 0.7)

intensity = np.maximum(1 + wave1 + wave2 + wave3, 0)

probability = intensity / intensity.sum()


sampled_timestamps = np.random.choice(
    t,
    size=500,
    p=probability
)


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

plt.plot(t, wave1, alpha=0.4, label="Wave 1")
plt.plot(t, wave2, alpha=0.4, label="Wave 2")
plt.plot(t, wave3, alpha=0.4, label="Wave 3")

plt.plot(t, intensity, linewidth=3, label="Combined intensity")

plt.xlabel("Time (s)")
plt.ylabel("Intensity")
plt.title("Superposition of sine waves")
plt.legend()

plt.tight_layout()
plt.show()

# -------------------------------------------probability-------------------------------------


plt.figure(figsize=(12, 4))

plt.plot(t, probability)

plt.fill_between(t, probability, alpha=0.3)

plt.xlabel("Time (s)")
plt.ylabel("Probability")
plt.title("Normalized probability distribution")

plt.tight_layout()
plt.show()


# --------------- histogram --------------

plt.figure(figsize=(12, 4))

plt.hist(sampled_timestamps, bins=30)

plt.xlabel("Time (s)")
plt.ylabel("Requests")
plt.title("Request density over time")

plt.tight_layout()
plt.show()
