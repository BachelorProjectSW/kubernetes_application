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

        <div className="section-panel">
            <div className="panel-title">🧠 Cluster Configurations</div>
            <div key={index} className="field-row">
                <input
                    placeholder="Name"
                    value={cluster.name || ""}
                    onChange={(e) => updateCluster(index, "name", e.target.value)}
                />

                <input
                    placeholder="Port"
                    type="number"
                    value={cluster.port || ""}
                    onChange={(e) => updateCluster(index, "port", e.target.value)}
                />

                <div className="field-group">
                    <label>GPIO</label>
                    <div className="inline-fields">
                        {(cluster.gpio_list || []).map((pin, pinIdx) => (
                            <div key={pinIdx} className="field-row">
                                <input
                                    type="number"
                                    value={pin}
                                    onChange={(e) => {
                                        const newList = [...cluster.gpio_list];
                                        newList[pinIdx] = parseInt(e.target.value) || 0;
                                        updateCluster(index, "gpio_list", newList);
                                    }}
                                />
                                <button type="button" onClick={() => {
                                    const newList = cluster.gpio_list.filter((_, i) => i !== pinIdx);
                                    updateCluster(index, "gpio_list", newList);
                                }}>
                                    ✕
                                </button>
                            </div>
                        ))}
                    </div>

                    <button type="button" onClick={() => {
                        const newList = [...(cluster.gpio_list || []), 0];
                        updateCluster(index, "gpio_list", newList);
                    }}>
                        + Add Pin
                    </button>
                </div>

                <button type="button" onClick={() => removeCluster(index)}>
                    ✕
                </button>
            </div>
        </div>
    )
}

export default ClusterMangening;
