function StratoConfigs({ inputs, handleChange }) {
  return (
    <>
      <p className="panel-title">
        <span className="panel-title-icon">🛰️</span>
        Strato Config
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
        <label
          style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}
        >
          <span
            style={{
              fontSize: "0.68rem",
              color: "var(--text-label)",
              letterSpacing: "0.04em",
            }}
          >
            IP Address
          </span>
          <input
            type="text"
            name="ip_strato"
            value={inputs.ip_strato || ""}
            onChange={handleChange}
            placeholder="e.g. 192.168.1.2"
            style={{ width: "100%" }}
          />
        </label>

        <label
          style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}
        >
          <span
            style={{
              fontSize: "0.68rem",
              color: "var(--text-label)",
              letterSpacing: "0.04em",
            }}
          >
            Port
          </span>
          <input
            type="number"
            name="port_strato"
            value={inputs.port_strato || ""}
            onChange={handleChange}
            placeholder="e.g. 9090"
            style={{ width: "100%" }}
          />
        </label>
      </div>
    </>
  );
}

export default StratoConfigs;
