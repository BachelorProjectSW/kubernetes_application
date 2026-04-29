function ClusterMangening({ inputs, setInputs }) {
    const clusters = inputs.clusters || [];

    const addCluster = () => {
        setInputs(prev => ({
            ...prev,
            clusters: [
                ...(prev.clusters || []),
                { name: "", ip: "", port: undefined, gpio_list: [], simulated_country_code: "", k3d: undefined }
            ]
        }));
    };

    const updateCluster = (index, field, value) => {
        setInputs(prev => {
            const updatedClusters = [...(prev.clusters || [])];
            updatedClusters[index] = { ...updatedClusters[index], [field]: value };
            return { ...prev, clusters: updatedClusters };
        });
    };

    const removeCluster = (index) => {
        setInputs(prev => ({
            ...prev,
            clusters: (prev.clusters || []).filter((_, i) => i !== index)
        }));
    };

    return (
        <>
            <p className="panel-title">
                <span className="panel-title-icon">🖥️</span>
                Cluster Configurations
                <span style={{
                    marginLeft: "auto",
                    background: "var(--accent-soft)",
                    border: "1px solid rgba(0,230,180,0.25)",
                    color: "var(--accent)",
                    borderRadius: "12px",
                    padding: "0.1rem 0.6rem",
                    fontSize: "0.68rem",
                    fontWeight: 600
                }}>
                    {clusters.length} cluster{clusters.length !== 1 ? "s" : ""}
                </span>
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {clusters.length === 0 && (
                    <div style={{
                        textAlign: "center",
                        padding: "1.5rem",
                        color: "var(--text-muted)",
                        fontSize: "0.75rem",
                        border: "1px dashed var(--border)",
                        borderRadius: "var(--radius)",
                        letterSpacing: "0.04em"
                    }}>
                        No clusters configured — add one below
                    </div>
                )}

                {clusters.map((cluster, index) => (
                    <div key={index} style={{
                        background: "var(--surface-2)",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius)",
                        padding: "1rem 1.1rem",
                    }}>
                        {/* Cluster header */}
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.85rem" }}>
                            <span style={{
                                fontFamily: "var(--display)",
                                fontSize: "0.7rem",
                                fontWeight: 700,
                                letterSpacing: "0.12em",
                                textTransform: "uppercase",
                                color: "var(--text-muted)"
                            }}>
                                Cluster {String(index + 1).padStart(2, "0")}
                                {cluster.name && <span style={{ color: "var(--accent)", marginLeft: "0.5rem" }}>— {cluster.name}</span>}
                            </span>
                            <button
                                type="button"
                                onClick={() => removeCluster(index)}
                                style={{ color: "red", border: "1px solid red", background: "none", cursor: "pointer" }}
                            >
                                ✕ Remove
                            </button>
                        </div>

                        {/* Main fields */}
                        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                            <label style={{ display: "flex", flexDirection: "column", gap: "0.3rem", flex: "1 1 120px" }}>
                                <span style={{ fontSize: "0.62rem", color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Name</span>
                                <input
                                    placeholder="node-eu-1"
                                    value={cluster.name || ""}
                                    onChange={(e) => updateCluster(index, "name", e.target.value)}
                                />
                            </label>

                            <label style={{ display: "flex", flexDirection: "column", gap: "0.3rem", flex: "1 1 140px" }}>
                                <span style={{ fontSize: "0.62rem", color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>IP Address</span>
                                <input
                                    placeholder="192.168.1.x"
                                    value={cluster.ip || ""}
                                    onChange={(e) => updateCluster(index, "ip", e.target.value)}
                                />
                            </label>

                            <label style={{ display: "flex", flexDirection: "column", gap: "0.3rem", flex: "0 0 90px" }}>
                                <span style={{ fontSize: "0.62rem", color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Port</span>
                                <input
                                    placeholder="8080"
                                    type="number"
                                    value={cluster.port || ""}
                                    onChange={(e) => updateCluster(index, "port", e.target.value)}
                                    style={{ width: "100%" }}
                                />
                            </label>

                            <label style={{ display: "flex", flexDirection: "column", gap: "0.3rem", flex: "0 0 100px" }}>
                                <span style={{ fontSize: "0.62rem", color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Country Code</span>
                                <input
                                    placeholder="e.g. DE"
                                    type="text"
                                    value={cluster.simulated_country_code || ""}
                                    onChange={(e) => updateCluster(index, "simulated_country_code", e.target.value)}
                                    style={{ width: "100%" }}
                                />
                            </label>
                        </div>

                        {/* GPIO pins */}
                        <div>
                            <span style={{ fontSize: "0.62rem", color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase", display: "block", marginBottom: "0.4rem" }}>
                                GPIO Pins
                            </span>
                            <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center" }}>
                                {(cluster.gpio_list || []).map((pin, pinIdx) => (
                                    <div key={pinIdx} style={{ display: "flex", alignItems: "center", gap: "2px" }}>
                                        <input
                                            type="number"
                                            value={pin}
                                            onChange={(e) => {
                                                const newList = [...cluster.gpio_list];
                                                newList[pinIdx] = parseInt(e.target.value) || 0;
                                                updateCluster(index, "gpio_list", newList);
                                            }}
                                            style={{ width: "54px", textAlign: "center" }}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => {
                                                const newList = cluster.gpio_list.filter((_, i) => i !== pinIdx);
                                                updateCluster(index, "gpio_list", newList);
                                            }}
                                            style={{ border: "none", background: "none", color: "red", cursor: "pointer", padding: "0 2px" }}
                                        >
                                            ✕
                                        </button>
                                    </div>
                                ))}
                                <button
                                    type="button"
                                    onClick={() => {
                                        const newList = [...(cluster.gpio_list || []), 0];
                                        updateCluster(index, "gpio_list", newList);
                                    }}
                                    style={{ fontSize: "0.72rem", padding: "0.25rem 0.55rem" }}
                                >
                                    + Pin
                                </button>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            <button
                type="button"
                onClick={addCluster}
                style={{ marginTop: "0.85rem", width: "100%", padding: "0.55rem", justifyContent: "center" }}
            >
                + Add Cluster
            </button>
        </>
    );
}

export default ClusterMangening;
