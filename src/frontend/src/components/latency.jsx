function Latency({ inputs, handleChange }) {
  return (
    <>
      <p className="panel-title">
        <span className="panel-title-icon">📡</span>
        Latency
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
        <label
          style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}
        >
          <span
            data-tooltip="Rolling window in seconds for latency measurement"
            style={{
              fontSize: "0.68rem",
              color: "var(--text-label)",
              letterSpacing: "0.04em",
            }}
          >
            Latency Window (s)
          </span>
          <input
            type="number"
            name="latency_window"
            value={inputs.latency_window || ""}
            onChange={handleChange}
            placeholder="e.g. 60"
            style={{ width: "100%" }}
          />
        </label>

        <label
          style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}
        >
          <span
            data-tooltip="Maximum allowed latency in milliseconds"
            style={{
              fontSize: "0.68rem",
              color: "var(--text-label)",
              letterSpacing: "0.04em",
            }}
          >
            Max Latency (ms)
          </span>
          <input
            type="number"
            name="max_latency"
            value={inputs.max_latency || ""}
            onChange={handleChange}
            placeholder="e.g. 500"
            style={{ width: "100%" }}
          />
        </label>
      </div>
    </>
  );
}

export default Latency;
