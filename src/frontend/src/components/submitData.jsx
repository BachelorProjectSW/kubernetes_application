/*class Config(BaseModel):
    """Config."""

    id: str
    name: str
    start: StartConfig
    weights: WeightsConfig
    power_scheduler: PowerSchedulerConfig
    latency: LatencyConfig
    workload: WorkloadConfig
    question: QuestionConfig
    clusters: list[ClusterConfig]
    global_scheduler: GlobalSchedulerConfig
    strato: StratoConfig
    energy: EnergyConfig = EnergyConfig()

*/



export const handleSubmit = async (e, inputs) => {
    e.preventDefault();

    // Perform the conversion here
    const days = parseInt(inputs.dur_days) || 0;
    const hours = parseInt(inputs.dur_hours) || 0;
    const minutes = parseInt(inputs.dur_minutes) || 0;

    const totalSeconds = (days * 86400) + (hours * 3600) + (minutes * 60);


    const exportData = {
        id: inputs.expID || "",
        name: inputs.name || "",
        start: {
            duration_time_s: totalSeconds,
            start_time: inputs.startdate || "",
        } || "",
        weights: {
            gco2: inputs.gco2,
            cost: inputs.cost
        } || "",
        power_scheduler: {
            timeout_s: inputs.timeout_s,
            idle_time_for_turn_off_s: inputs.turn_off_s
        } || "",
        latency: {
            max_latency: inputs.max_latency || "",
        },
        workload: {
            request_pr_min: inputs.request_pr_min,
            pattern: inputs.pattern,
            seed: inputs.seed,
            peakiness: inputs.peakiness
        } || "",
        question: {
            question: inputs.question,
            max_output_tokens: inputs.max_output_tokens,
            context_window: inputs.context_window
        } || "",
        clusters: (inputs.clusters || []).map((cluster) => ({
            name: cluster.name || "",
            ip: cluster.ip || "",
            port: cluster.port || "",
            gpio_list: cluster.gpio_list ||"",
            simulated_country_code: cluster.simulated_country_code || "",
            llama_service_port: cluster.llama_service_port || ""
        })),
        global_scheduler: {
            ip: inputs.ip_global,
            port: inputs.port_global
        } || "",
        strato: {
            ip: inputs.ip_strato,
            port: inputs.port_strato
        } || ""
    };

try {
        const response = await fetch('http://127.0.0.1:8090/start_test', { // Ensure port matches your FastAPI server
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(exportData),
        });

        if (!response.ok) {
            const errorDetail = await response.json();
            console.error("Validation Error:", errorDetail);
            alert("Failed to start test. Check console for details.");
            return;
        }

        const data = await response.json();
        console.log("Success:", data);
        alert("Test started successfully!");
    } catch (error) {
        console.error("Network Error:", error);
        alert("Could not connect to the backend.");
    }
     console.log(JSON.stringify(exportData, null, 2));
};


