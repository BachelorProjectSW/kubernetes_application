function Start({ inputs, handleChange }) {
  return (
    <>
      <p className="panel-title">
        <span className="panel-title-icon">🕒</span>
        Timing
      </p>

      <div
        style={{
          display: "flex",
          gap: "2rem",
          flexWrap: "wrap",
          alignItems: "flex-end",
        }}
      >
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
            Simulated Start Date &amp; Time
          </span>
          <input
            type="datetime-local"
            name="startdate"
            value={inputs.startdate || ""}
            onChange={handleChange}
          />
        </label>

        <div>
          <span
            style={{
              fontSize: "0.68rem",
              color: "var(--text-label)",
              letterSpacing: "0.04em",
              display: "block",
              marginBottom: "0.45rem",
            }}
          >
            Duration
          </span>
          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
            <label
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.3rem",
                alignItems: "center",
              }}
            >
              <input
                type="number"
                name="dur_days"
                min="0"
                style={{ width: "64px", textAlign: "center" }}
                value={inputs.dur_days || 0}
                onChange={handleChange}
              />
              <span
                style={{
                  fontSize: "0.62rem",
                  color: "var(--text-muted)",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                Days
              </span>
            </label>

            <span
              style={{
                color: "var(--text-muted)",
                fontSize: "1rem",
                paddingBottom: "1.1rem",
              }}
            >
              :
            </span>

            <label
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.3rem",
                alignItems: "center",
              }}
            >
              <input
                type="number"
                name="dur_hours"
                min="0"
                max="23"
                style={{ width: "64px", textAlign: "center" }}
                value={inputs.dur_hours || 0}
                onChange={handleChange}
              />
              <span
                style={{
                  fontSize: "0.62rem",
                  color: "var(--text-muted)",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                Hours
              </span>
            </label>

            <span
              style={{
                color: "var(--text-muted)",
                fontSize: "1rem",
                paddingBottom: "1.1rem",
              }}
            >
              :
            </span>

            <label
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.3rem",
                alignItems: "center",
              }}
            >
              <input
                type="number"
                name="dur_minutes"
                min="0"
                max="59"
                style={{ width: "64px", textAlign: "center" }}
                value={inputs.dur_minutes || 0}
                onChange={handleChange}
              />
              <span
                style={{
                  fontSize: "0.62rem",
                  color: "var(--text-muted)",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                Min
              </span>
            </label>
          </div>
        </div>
      </div>
    </>
  );
}

export default Start;
