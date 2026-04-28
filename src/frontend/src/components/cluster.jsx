
/*
"clusters": (inputs.clusters || []).map((cluster) => ({
            "name": cluster.name || "", //str
            "ip": "",
            "port": cluster.port || "", //str
            "gpio_list": cluster.gpio_list || "", // list[int]
            "simulated_country_code": cluster.simulated_country_code || "",  //str
            "llama_service_port": "",
            "renewable_output_w": "",
            "cluster_load_w": "",
            "grid_carbon_intensity": "",
            "grid_electricity_price": "",
            "k3d": false
        })),



    example: 
     "name": "dk",
      "ip": "100.114.88.102",
      "port": "8033",
      "gpio_list": [17, 27, 23],
      "simulated_country_code": "ES",
      "llama_service_port": "8083",
      "renewable_output_w": 200,
      "cluster_load_w": 1000,
      "grid_carbon_intensity": 100,
      "grid_electricity_price": 0.12,
      "k3d": false
    */

function ClusterMangening({ inputs, setInputs }) {
    const clusters = inputs.clusters || []


    const addCluster = () => {
        setInputs(prev => ({
            ...prev,
            clusters: [
                ...(prev.clusters || []),
                {
                    "name": "",
                    "ip": "",
                    "port": null,
                    "gpio_list": [],
                    "simulated_country_code": "",
                    "llama_service_port": null,
                    "renewable_output_w": null,
                    "cluster_load_w": null,
                    "grid_carbon_intensity": null,
                    "grid_electricity_price": null,
                    "k3d": null
                }
            ]
        }));
    };


    const updateCluster = (index, field, value) => {
        setInputs(prev => {
            const updatedClusters = [...(prev.clusters || [])];

            updatedClusters[index] = {
                ...updatedClusters[index],
                [field]: value
            };

            return {
                ...prev,
                clusters: updatedClusters
            };
        });
    };

    const removeCluster = (index) => {
        const newClusters = (inputs.clusters || []).filter((_, i) => i !== index);
        setInputs(prev => ({
            ...prev,
            clusters: newClusters
        }));
    };

    return (
        <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
            <p><strong>Cluster Configurations</strong></p>

            {clusters.map((cluster, index) => (
                <div key={index} style={{ display: "flex", gap: "10px", marginBottom: "10px", alignItems: "center" }}>
                    <input
                        placeholder="Name"
                        value={cluster.name || ""}
                        onChange={(e) => updateCluster(index, "name", e.target.value)}
                        style={{ width: "100px" }}
                    />

                    <input
                        placeholder="Port"
                        type="number"
                        value={cluster.port || ""}
                        onChange={(e) => updateCluster(index, "port", e.target.value)}
                        style={{ width: "70px" }}
                    />
                    <div>
                        <label>GPIO Pins:</label>
                        {(cluster.gpio_list || []).map((pin, pinIdx) => (
                            <input
                                key={pinIdx}
                                type="number"
                                value={pin}
                                onChange={(e) => {
                                    const newList = [...cluster.gpio_list];
                                    newList[pinIdx] = parseInt(e.target.value);
                                    updateCluster(index, "gpio_list", newList);
                                }}
                                style={{ width: "50px", marginRight: "5px" }}
                            />
                        ))}
                        <button type="button" onClick={() => {
                            const newList = [...(cluster.gpio_list || []), 0];
                            updateCluster(index, "gpio_list", newList);
                        }}>
                            +
                        </button>
                    </div>
                    <input
                        placeholder="simulated country code"
                        type="text"
                        value={cluster.simulated_country_code || ""}
                        onChange={(e) => updateCluster(index, "simulated_country_code", e.target.value)}
                        style={{ width: "70px" }}
                    />
                    <input
                        placeholder="llama service port"
                        type="number"
                        value={cluster.llama_service_port || ""}
                        onChange={(e) => updateCluster(index, "llama_service_port", e.target.value)}
                        style={{ width: "70px" }}
                    />
                    <button
                        type="button"
                        onClick={() => removeCluster(index)}
                        style={{ color: "red", border: "1px solid red", background: "none", cursor: "pointer" }}
                    >
                        ✕
                    </button>
                </div>
            ))}

            <button type="button" onClick={addCluster}>
                + Add Cluster
            </button>
        </div>
    );
}

export default ClusterMangening;