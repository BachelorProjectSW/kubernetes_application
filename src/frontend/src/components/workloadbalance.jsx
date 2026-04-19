
function Workload({ inputs, handleChange }) {

    return (
        <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
            <p>Workload configurations</p>

            <div style={{ display: "flex", gap: "10px", marginTop: "5px" }}>
                <label> Requests pr. Minute</label>
                <input
                    type="number"
                    name="request_pr_min"
                    value={inputs.request_pr_min || ""}
                    onChange={handleChange}
                />
            </div>
            <div style={{ display: "flex", gap: "10px", marginTop: "5px" }}>
                <label>Pattern
                    <select
                        name="pattern"
                        value={inputs.pattern || ""}
                        onChange={handleChange}
                    >
                        <option value="" disabled>Select a pattern</option>
                        <option value="steady">steady</option>
                        <option value="peaks">peaks</option>
                    </select>
                </label>
            </div>
            <div style={{ display: "flex", gap: "10px", marginTop: "5px" }}>
                <label> Seeds</label>
                <input
                    type="number"
                    name="seed"
                    value={inputs.seed}
                    onChange={handleChange}
                />
            </div>


            <div style={{ display: "flex", gap: "10px", marginTop: "5px" }}>
                <label>Peakiness</label>
                <input
                    type="number"
                    name="peakiness"
                    value={inputs.peakiness}
                    onChange={handleChange}
                />

                <div />

            </div>

        </div>


    )
}
export default Workload;