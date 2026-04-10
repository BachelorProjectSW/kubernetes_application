export const handleSubmit = async (e, inputs) => {
    e.preventDefault();

    // Perform the conversion here
    const days = parseInt(inputs.dur_days) || 0;
    const hours = parseInt(inputs.dur_hours) || 0;
    const minutes = parseInt(inputs.dur_minutes) || 0;

    const totalSeconds = (days * 86400) + (hours * 3600) + (minutes * 60);

    const exportData = {
        id: inputs.exID || "",
        name: inputs.name || "",
        start: {
            duration_time_s: inputs.duration,
            start_time: totalSeconds || "",
        } || "",
        weights: {
            gco2: inputs.gco2,
            cost: inputs.cost
        } || "",
        power_scheduler: {
            timeout_s: inputs.timeout_s,
            idle_time_for_turn_off_s: inputs.turn_off_s
        } || "",
        max_latency: inputs.max_latency || "",
        workload: {
            request_per_minute: inputs.request_interval,
            pattern: inputs.pattern,
            seed: inputs.seed,
            peakiness: inputs.peakiness
        } || "",
        question: {
            question: inputs.question,
            max_output_tokens: inputs.max_output_tokens,
            context_window: inputs.context_window
        } || "",
        clusters: inputs.clusters || "", // make funktion for submitting the correct amount of clusters.
        global_scheduler: {
            ip: inputs.global_ip,
            port: inputs.global_ports
        } || "",
        strato: {
            ip: inputs.strato_ip,
            port: inputs.strato_ports
        } || ""
    };


    // try {
    //   const response = await fetch('http://127.0.0.1:8040/save-config', { // lav endpoint i backend. hvor navn er save-config 
    //     method: 'POST',
    //   headers: {
    //     'Content-Type': 'application/json',
    // },
    // body: JSON.stringify(exportData),
    //});

    //const data = await response.json();
    //console.log("Response from FastAPI:", data);
    //alert("Data sent successfully!");
    //} catch (error) {
    //  console.error("Error connecting to FastAPI:", error);
    //}
    console.log("Sending these configurations:", inputs);
}