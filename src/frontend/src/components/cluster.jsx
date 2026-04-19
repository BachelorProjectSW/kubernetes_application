function ClusterMangening({inputs, setInputs}){
    const clusters = inputs.clusters || []


    const addCluster =() => {
    setInputs(prev => ({
        ...prev,
        clusters: [
            ...(prev.clusters || []), 
            { 
                name: "", 
                ip: "", 
                port: "", 
                gpio_list:"",
                simulated_country_code: "", 
                llama_service_port: "" 
            }
        ]
    }));
};


const updateCluster =(index, field, value) => {
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
                        placeholder="IP Address"
                        value={cluster.ip || ""}
                        onChange={(e) => updateCluster(index, "ip", e.target.value)}
                        style={{ width: "120px" }}
                    />
                    <input
                        placeholder="Port"
                        type="number"
                        value={cluster.port || ""}
                        onChange={(e) => updateCluster(index, "port", e.target.value)}
                        style={{ width: "70px" }}
                    />
                     <input
                        placeholder="gpiolist"
                        type="number"
                        value={cluster.gpio_list || ""}
                        onChange={(e) => updateCluster(index, "gpio_list", e.target.value)}
                        style={{ width: "70px" }}
                    />
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