function Latency({inputs, handleChange}) {

       return (
        <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
            <p> Latency </p>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label> latency window</label>
                    <input 
                        type="number"
                        name="latency_window"
                        value={inputs.latency_window}
                        onChange={handleChange} />
                
            </div>
             <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label>max latency in ms</label>
                    <input
                        type="number"
                        name="max_latency"
                        value={inputs.max_latency} 
                        onChange={handleChange}/>
             </div>
        </div>
    );
}

export default Latency;
