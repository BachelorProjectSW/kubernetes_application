function GlobalScheduler({ inputs, handleChange }) {
  return (
    <>
      <p className="panel-title">
        <span className="panel-title-icon">🌐</span>
        Global Scheduler
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
            name="ip_global"
            value={inputs.ip_global || ""}
            onChange={handleChange}
            placeholder="e.g. 192.168.1.1"
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
            name="port_global"
            value={inputs.port_global || ""}
            onChange={handleChange}
            placeholder="e.g. 8080"
            style={{ width: "100%" }}
          />
        </label>
      </div>
    </>
  );
}

export default GlobalScheduler;
