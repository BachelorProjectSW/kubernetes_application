function ClusterMangening({ inputs, setInputs }) {
  const clusters = inputs.clusters || [];

  const addCluster = () => {
    setInputs((prev) => ({
      ...prev,
      clusters: [
        ...(prev.clusters || []),
        {
          name: "",
          ip: "",
          port: undefined,
          gpio_list: [],
          simulated_country_code: "",
          k3d: undefined,
        },
      ],
    }));
  };

  const updateCluster = (index, field, value) => {
    setInputs((prev) => {
      const updatedClusters = [...(prev.clusters || [])];

      updatedClusters[index] = {
        ...updatedClusters[index],
        [field]: value,
      };

      return {
        ...prev,
        clusters: updatedClusters,
      };
    });
  };

  const removeCluster = (index) => {
    const newClusters = (inputs.clusters || []).filter((_, i) => i !== index);
    setInputs((prev) => ({
      ...prev,
      clusters: newClusters,
    }));
  };

  return (
    <div
      style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}
    >
      <p>
        <strong>Cluster Configurations</strong>
      </p>

      {clusters.map((cluster, index) => (
        <div
          key={index}
          style={{
            display: "flex",
            gap: "10px",
            marginBottom: "10px",
            alignItems: "center",
          }}
        >
          <input
            placeholder="Name"
            value={cluster.name || ""}
            onChange={(e) => updateCluster(index, "name", e.target.value)}
            style={{ width: "100px" }}
          />

          <input
            placeholder="IP adress"
            value={cluster.ip || ""}
            onChange={(e) => updateCluster(index, "ip", e.target.value)}
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
              <div
                key={pinIdx}
                style={{ display: "inline-block", marginRight: "5px" }}
              >
                <input
                  type="number"
                  value={pin}
                  onChange={(e) => {
                    const newList = [...cluster.gpio_list];
                    newList[pinIdx] = parseInt(e.target.value) || 0;
                    updateCluster(index, "gpio_list", newList);
                  }}
                  style={{ width: "50px" }}
                />

                <button
                  type="button"
                  onClick={() => {
                    const newList = cluster.gpio_list.filter(
                      (_, i) => i !== pinIdx,
                    );
                    updateCluster(index, "gpio_list", newList);
                  }}
                  style={{
                    border: "none",
                    background: "none",
                    color: "red",
                    cursor: "pointer",
                    padding: "0 2px",
                  }}
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
            >
              +
            </button>
          </div>
          <input
            placeholder="simulated country code"
            type="text"
            value={cluster.simulated_country_code || ""}
            onChange={(e) =>
              updateCluster(index, "simulated_country_code", e.target.value)
            }
            style={{ width: "70px" }}
          />
          <button
            type="button"
            onClick={() => removeCluster(index)}
            style={{
              color: "red",
              border: "1px solid red",
              background: "none",
              cursor: "pointer",
            }}
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
