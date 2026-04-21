export const handleSubmit = async (e, inputs) => {
    e.preventDefault();

    // Perform the conversion here
    const days = parseInt(inputs.dur_days) || 0;
    const hours = parseInt(inputs.dur_hours) || 0;
    const minutes = parseInt(inputs.dur_minutes) || 0;

    const totalSeconds = (days * 86400) + (hours * 3600) + (minutes * 60);


    const exportData = {

        /*start: {
            duration_time_s: totalSeconds || "",
            start_time_simulated: inputs.startdate || "", // opdater andre steder
            start_time_real: null
        } || "",

        weights: {
            gco2: inputs.gco2,
            cost: inputs.cost,
            latency: inputs.latency || "2"// opdater andre steder
        } || "",
        power_scheduler: {
            start: true,
            timeout_s: inputs.timeout_s,
            idle_time_for_turn_off_s: inputs.turn_off_s
        } || "",
        latency: {
            latency_windows_s: inputs.window || "34", //opdater andre steder
            max_latency: inputs.max_latency || "",
        },
        workload: {
            request_pr_minute: inputs.request_pr_min, // opdate?
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
            gpio_list: cluster.gpio_list || "",
            simulated_country_code: cluster.simulated_country_code || "",
            llama_service_port: cluster.llama_service_port || "",
            renewable_output_w: "200",
            cluster_load_w: "1000",
            grid_carbon_intensity: "100",
            grid_electricity_price: "0.12",
            k3d: false
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

  
    "latency": {
        "latency_windows_s": inputs.window || "", //opdater andre steder
        "max_latency": inputs.max_latency || "",
    },
    "workload": {
        "request_pr_minute": inputs.request_pr_min, // opdate?
        "gpio_list": cluster.gpio_list || "", // lav om til array 
        "simulated_country_code": stringify(cluster.simulated_country_code) || "",
        "llama_service_port": stringify(cluster.llama_service_port) || "",
        "renewable_output_w": 200, //should be hardcoded and  
        "cluster_load_w": 1000, //should be hardcodede d
        
   
*/
        "id": inputs.expID || "",
        "name": inputs.name || "",
        "start": {
            "duration_time_s": totalSeconds || "",
           "start_time_simulated": "01/10/2021",
            "start_time_real": null
        } || "",
        "weights": {
            "gco2": inputs.gco2,
            "cost": inputs.cost,
           "latency": inputs.latency || "2"// opdater andre steder
        } || "",
        "power_scheduler": {
          "start": true,
            "timeout_s": inputs.timeout_s,
            "idle_time_for_turn_off_s": inputs.turn_off_s
        } || "",
        "latency": { //lav fil til dette
           "latency_windows_s": inputs.window || "34", //opdater andre steder
            "max_latency": inputs.max_latency || "",
        },
        "workload": {
            "request_per_minute": 10,
            "pattern": "steady",
            "seed": 10,
            "peakiness": 0
        },
        "question": {
            "question": "hey",
            "max_output_tokens": 200,
            "context_window": 200
        },
        "clusters": [
            {
                "name": "dk",
                "ip": "100.114.88.102",
                "port": "8033",
                "gpio_list": [17, 27, 23],
                "simulated_country_code": "ES",
                "llama_service_port": "8083",
                "renewable_output_w": 200,
                "cluster_load_w": 1000,
                "grid_carbon_intensity": 100,
                "grid_electricity_price": 0.12,
                "k3d": false
            },
            {
                "name": "pt",
                "ip": "100.83.243.61",
                "port": "8033",
                "gpio_list": [17, 27, 23],
                "simulated_country_code": "pt",
                "llama_service_port": "8082",
                "renewable_output_w": 400,
                "cluster_load_w": 1000,
                "grid_carbon_intensity": 300,
                "grid_electricity_price": 0.14,
                "k3d": false
            }
        ],
        "global_scheduler": {
            "ip": "100.84.252.101",
            "port": "8022"
        },
        "strato": {
            "ip": "100.109.95.2",
            "port": "8011"
        }

    };

    try {
        console.log(exportData);
        const response = await fetch('http://100.109.95.2:8095/start_test', { // Ensure port matches your FastAPI server
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


