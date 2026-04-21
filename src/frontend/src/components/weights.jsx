
function Weights({ inputs, handleChange }) {

 return (
        <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
            <p>Weights</p>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label>gco2:</label>
                <input 
                    type="range" 
                    name="gco2" 
                    min="0" 
                    max="1" 
                    step="0.01"
                    value={inputs.gco2 || 0.5} 
                    onChange={handleChange} 
                />

                <span style={{ fontWeight: "bold", color: "#007bff" }}>
                    {inputs.gco2 || 0.5}
                </span>
            </div>

            <br/>
             <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label>cost:</label>
                <input 
                    type="range"
                    name="cost" 
                    min="0" 
                    max="1" 
                    step="0.01"
                    value={inputs.cost || 0.5} 
                    onChange={handleChange} 
                />
               
                <span style={{ fontWeight: "bold", color: "#007bff" }}>
                    {inputs.cost || 0.5}
                </span>
            </div>
        <br/>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label>latency:</label>
                <input 
                    type="range" 
                    name="weight_latency" 
                    min="0" 
                    max="1" 
                    step="0.01"
                    value={inputs.weight_latency || 0.5} 
                    onChange={handleChange}
                />

                <span style={{ fontWeight: "bold", color: "#007bff" }}>
                    {inputs.weight_latency || 0.5}
                </span>
            </div>
        </div>
    );
}

export default Weights;