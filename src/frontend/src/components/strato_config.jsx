
function StratoConfigs({ inputs, handleChange }) {

    return (
        <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
            <p> Strato configurations</p>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label> Ip adress </label>
                <input
                    type="text"
                    name="ip_strato "
                    value={inputs.ip_strato}
                    onChange={handleChange} />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label> Port </label>
                <input
                    type="number"
                    name="port_strato"
                    value={inputs.port_strato}
                    onChange={handleChange}/>
            </div>
        </div>
    )
}

export default StratoConfigs;