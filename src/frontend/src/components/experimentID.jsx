import { useState } from "react";
import earlierExpIds from './staticData';

function Ids({ inputs, setInputs, handleChange }) {

    const [isExisting, setIsExisting] = useState(false);
    const toggleMode = () => setIsExisting(!isExisting);

    const handleSelectHistory = (e) => {
        const selectedId = e.target.value;
        if (!selectedId) return;

        const historicalData = earlierExpIds.find(exp => exp.id == selectedId);

        if (historicalData) {
            setInputs(prev => ({
                ...prev,
                expID: historicalData.id,
                name: historicalData.name,
                startdate: historicalData.startdate,
                dur_days: historicalData.dur_days,
                dur_hours: historicalData.dur_hours, 
                dur_minutes: historicalData.dur_minutes, 
                gco2: historicalData.gco2, 
                cost: historicalData.cost,
                latency: historicalData.latency,
                timeout_s: historicalData.timeout_s,
                turn_off_s:historicalData.turn_off_s,
                window:historicalData.window,
                max_latency: historicalData.max_latency,
                request_pr_min: historicalData.request_pr_min,
                pattern: historicalData.pattern,
                seed:historicalData.seed,
                peakiness: historicalData.peakiness,
                clusters: historicalData.clusters || [],
                ip_global:historicalData.ip_global,
                port_global:historicalData.port_global,
                ip_strato:historicalData.ip_strato,
                port_strato:historicalData.port_strato
            }));
        }
    };


    return (
        <>
            <label> ExpId:
            <button type="button"
                onClick={toggleMode}
                style={{ marginLeft: "10px", fontSize: "0.8em" }}
            >
                {isExisting ? "Switch to New ID" : "Select Existing ID"}
            </button>

            <br />

            {
                isExisting ? (
                    <select name="expID" onChange={handleSelectHistory}>
                        <option value="">-- Select an ID --</option>
                        {earlierExpIds.map(exp => (
                            <option key={exp.id} value={exp.id}>{exp.id}</option>
                        ))}
                    </select>
                ) : (
                    <input
                        type="text"
                        name="expID"
                        value={inputs.expID || ""}
                        onChange={handleChange}
                    />
                )
            }
            </label>
        </>
    );

}

export default Ids;
