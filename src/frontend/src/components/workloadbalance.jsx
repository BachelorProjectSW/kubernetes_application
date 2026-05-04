function Workload({ inputs, handleChange }) {
    
    return (
        <>
            <p className="panel-title">
                <span className="panel-title-icon">📊</span>
                Workload
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                    <span style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}>
                        Requests / Minute
                    </span>
                    <input
                        type="number"
                        name="request_per_min"
                        value={inputs.request_per_min || ""}
                        onChange={handleChange}
                        placeholder="e.g. 100"
                        style={{ width: "100%" }}
                    />
                </label>

                <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                    <span style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}>
                        Traffic Pattern
                    </span>
                    <select
                        name="pattern"
                        value={inputs.pattern || ""}
                        onChange={handleChange}
                        style={{ width: "100%" }}
                    >
                        <option value="" disabled>Select a pattern</option>
                        <option value="steady">⟶ Steady</option>
                        <option value="peaks">▲ Peaks</option>
                    </select>
                </label>

                <div style={{ display: "flex", gap: "0.75rem" }}>
                    <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem", flex: 1 }}>
                        <span
                            data-tooltip="Random seed for reproducible traffic generation"
                            style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}
                        >
                            Seed
                        </span>
                        <input
                            type="number"
                            name="seed"
                            value={inputs.seed || ""}
                            onChange={handleChange}
                            placeholder="e.g. 42"
                        />
                    </label>

                    <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem", flex: 1 }}>
                        <span
                            data-tooltip="Sharpness of traffic peaks (peaks pattern only)"
                            style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}
                        >
                            Peakiness
                        </span>
                        <input
                            type="number"
                            name="peakiness"
                            value={inputs.peakiness || ""}
                            onChange={handleChange}
                            placeholder="e.g. 2.0"
                        />
                    </label>
                </div>
            </div>
        </>
    );
}

export default Workload;
