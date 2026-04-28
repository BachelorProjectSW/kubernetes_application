function GlobalScheduler({ inputs, handleChange }) {

    return (
        <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
            <p> Global Schedular</p>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label> Ip adress </label>
                <input
                    type="text"
                    name="ip_global"
                    value={inputs.ip_global}
                    onChange={handleChange} />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label> Port </label>
                <input
                    type="number"
                    name="port_global"
                    value={inputs.port_global}
                    onChange={handleChange} />
            </div>
        </div>
    )
}

export default GlobalScheduler;