function Weights({ inputs, handleChange }) {
  const sliders = [
    {
      name: "gco2",
      label: "CO₂ Weight",
      tooltip: "Priority weight for carbon emissions",
    },
    {
      name: "cost",
      label: "Cost Weight",
      tooltip: "Priority weight for energy cost",
    },
    {
      name: "latency",
      label: "Latency Weight",
      tooltip: "Priority weight for response latency",
    },
  ];

  return (
    <>
      <p className="panel-title">
        <span className="panel-title-icon">⚖️</span>
        Scheduler Weights
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {sliders.map(({ name, label, tooltip }) => (
          <div
            key={name}
            style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <label
                data-tooltip={tooltip}
                style={{ fontSize: "0.7rem", color: "var(--text-label)" }}
              >
                {label}
              </label>

              <input
                className="slider-value weight-input"
                type="number"
                name={name}
                min="0"
                max="1"
                step="0.01"
                value={inputs[name] ?? 0.5}
                onChange={handleChange}
              />
            </div>

            <input
              type="range"
              name={name}
              min="0"
              max="1"
              step="0.01"
              value={inputs[name] ?? 0.5}
              onChange={handleChange}
              style={{ width: "100%" }}
            />

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: "0.6rem",
                color: "var(--text-muted)",
              }}
            >
              <span>0.0</span>
              <span>0.5</span>
              <span>1.0</span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export default Weights;
