import { useState, useEffect } from "react";

function Ids({ inputs, setInputs, handleChange }) {
    const [earlierExpIds, setEarlierExpIds] = useState([]);
    const [isExisting, setIsExisting] = useState(false);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const fetchConfigs = async () => {
            setLoading(true);
            try {
                const response = await fetch('http://100.109.95.2:8099/get_configs');
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
                expID: entry.config_id,
                name: entry.config_name || config.name,
                startdate: formattedDate,
                dur_days: d, dur_hours: h, dur_minutes: m,
                gco2: config.weights?.gco2 ?? "",
                cost: config.weights?.cost ?? "",
                latency: config.weights?.latency ?? "",
                timeout_s: config.power_scheduler?.timeout_s ?? "",
                turn_off_s: config.power_scheduler?.idle_time_for_turn_off_s ?? "",
                latency_window: config.latency?.latency_window_s ?? "",
                max_latency: config.latency?.max_ms ?? "",
                request_per_min: config.workload?.request_per_minute ?? "",
                pattern: config.workload?.pattern || "",
                seed: config.workload?.seed ?? "",
                peakiness: config.workload?.peakiness ?? "",
                question: config.question?.question || "",
                max_output_tokens: config.question?.max_output_tokens ?? "",
                clusters: config.clusters || [],
                ip_global: config.global_scheduler?.ip || "",
                port_global: config.global_scheduler?.port ?? "",
                ip_strato: config.strato?.ip || "",
                port_strato: config.strato?.port ?? ""
            });
        }
    };

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <span style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}>
                    Experiment ID
                </span>
                <button
                    type="button"
                    onClick={toggleMode}
                    style={{ fontSize: "0.65rem !important", padding: "0.15rem 0.5rem !important" }}
                >
                    {isExisting ? "↩ New ID" : "📂 Load Existing"}
                </button>
                {loading && (
                    <span style={{ fontSize: "0.65rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                        fetching…
                    </span>
                )}
            </div>

            {isExisting ? (
                <select
                    name="expID"
                    onChange={handleSelectHistory}
                    style={{ minWidth: "180px" }}
                >
                    <option value="">— Select an experiment —</option>
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
                    placeholder="e.g. 1001"
                    style={{ width: "120px" }}
                />
            )}
        </div>
    );
}

export default Ids;
