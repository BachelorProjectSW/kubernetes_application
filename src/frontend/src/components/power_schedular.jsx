function Power_schedular({ inputs, handleChange }) {
    return (
        <>
            <p className="panel-title">
                <span className="panel-title-icon">🔋</span>
                Power Scheduler
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                    <span
                        data-tooltip="Seconds of inactivity before a node is considered idle"
                        style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}
                    >
                        Idle Timeout (s)
                    </span>
                    <input
                        type="number"
                        name="timeout_s"
                        value={inputs.timeout_s || ""}
                        onChange={handleChange}
                        placeholder="e.g. 300"
                        style={{ width: "100%" }}
                    />
                </label>

                <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                    <span
                        data-tooltip="Seconds after idle threshold before node powers off"
                        style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}
                    >
                        Turn-off Delay (s)
                    </span>
                    <input
                        type="number"
                        name="turn_off_s"
                        value={inputs.turn_off_s || ""}
                        onChange={handleChange}
                        placeholder="e.g. 60"
                        style={{ width: "100%" }}
                    />
                </label>
            </div>
        </>
    );
}

export default Power_schedular;
