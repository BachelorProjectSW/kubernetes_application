function Start({ inputs, handleChange }) {

    return (
        <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
            <label> StartDate:
                <input
                    type="datetime-local"
                    name="startdate"
                    value={inputs.startdate}
                    onChange={handleChange}
                />
            </label>

            <br />

            <p>Duration:</p>
            <div style={{ display: "flex", gap: "10px", marginTop: "5px" }}>
                <label> Days:
                    <input
                        type="number"
                        name="dur_days"
                        min="0"
                        style={{ width: "50px" }}
                        value={inputs.dur_days || 0}
                        onChange={handleChange}
                    />
                </label>
                <label> Hours:
                    <input
                        type="number"
                        name="dur_hours"
                        min="0"
                        max="23"
                        style={{ width: "50px" }}
                        value={inputs.dur_hours || 0}
                        onChange={handleChange}
                    />
                </label>
                <label> Minutes:
                    <input
                        type="number"
                        name="dur_minutes"
                        min="0"
                        max="59"
                        style={{ width: "50px" }}
                        value={inputs.dur_minutes || 0}
                        onChange={handleChange}
                    />
                </label>
            </div>
        <div/>
    </div>
    
    );
}

export default Start;