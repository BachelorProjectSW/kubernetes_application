import { useState, useEffect } from "react";

function Ids({ inputs, setInputs, handleChange }) {


    const [earlierExpIds, setEarlierExpIds] = useState([]);
    const [isExisting, setIsExisting] = useState(false);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const fetchConfigs = async () => {
            setLoading(true);
            try {
                const response = await fetch('http://100.109.95.2:8095/get_configs'); // Your backend IP
                if (!response.ok) throw new Error("Failed to fetch configs");
                const data = await response.json();
                setEarlierExpIds(data);
            } catch (err) {
                console.error("Error fetching historical data:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchConfigs();
    }, []);

    const toggleMode = () => setIsExisting(!isExisting);


const handleSelectHistory = (e) => {
    const selectedId = e.target.value;
    if (!selectedId) return;

    const entry = earlierExpIds.find(exp => exp.id == selectedId);

    if (entry && entry.config_json) {
        const config = entry.config_json;

        let formattedDate = "";
        if (config.start?.start_time_simulated) {
            
            const [datePart, timePart] = config.start.start_time_simulated.split(' ');
            const [day, month, year] = datePart.split('/');
            const [hours, minutes] = timePart.split(':');
            formattedDate = `${year}-${month}-${day}T${hours}:${minutes}`;
        }

        
        const totalSeconds = config.start?.duration_time_s || 0;
        const d = Math.floor(totalSeconds / 86400);
        const h = Math.floor((totalSeconds % 86400) / 3600);
        const m = Math.floor((totalSeconds % 3600) / 60);

        setInputs({
            // Identification
            expID: entry.config_id, 
            name: entry.config_name || config.name,
            
            // Start & Duration
            startdate: formattedDate,
            dur_days: d,
            dur_hours: h,
            dur_minutes: m,

            // Weights
            gco2: config.weights?.gco2 ?? "",
            cost: config.weights?.cost ?? "",
            latency: config.weights?.latency ?? "",

            // Power Scheduler
            timeout_s: config.power_scheduler?.timeout_s ?? "",
            turn_off_s: config.power_scheduler?.idle_time_for_turn_off_s ?? "",

            // Latency 
            latency_window: config.latency?.latency_window_s ?? "", 
            max_latency: config.latency?.max_ms ?? "",

            // Workload
            request_per_min: config.workload?.request_per_minute ?? "",
            pattern: config.workload?.pattern || "",
            seed: config.workload?.seed ?? "",
            peakiness: config.workload?.peakiness ??"",

            //Question
            question: config.question?.question ||"", 
            max_output_tokens: config.question?.max_output_tokens ?? "",

            // Cluster & Infrastructure
            clusters: config.clusters || [],
            ip_global: config.global_scheduler?.ip || "",
            port_global: config.global_scheduler?.port ?? "",
            ip_strato: config.strato?.ip || "",
            port_strato: config.strato?.port ?? ""
        });
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
                        type="number"
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
