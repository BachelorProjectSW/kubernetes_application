function Power_schedular({inputs, handleChange}) {



    return (
        <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
            <p> Schedual turn on</p>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label> node idle time  in seconds</label>
                    <input 
                        type="number"
                        name="timeout_s"
                        value={inputs.timeout_s}
                        onChange={handleChange} />
                
            </div>
             <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label>node turn off time</label>
                    <input
                        type="number"
                        name="turn_off_s"
                        value={inputs.turn_off_s} 
                        onChange={handleChange}/>
             </div>
        </div>
    );
}

export default Power_schedular;