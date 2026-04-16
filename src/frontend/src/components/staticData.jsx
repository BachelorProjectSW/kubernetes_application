const earlierExpIds = [
    {
        // Example 1: Standard AI Benchmark
        id: "EXP-001",
        name: "Llama-3-Base-Line",
        startdate: "2024-12-01T08:00",
        dur_days: 0,
        dur_hours: 2,
        dur_minutes: 30,
        gco2: 0.4,
        cost: 15,
        timeout_s: 300,
        turn_off_s: 600,
        max_latency: 100,
        request_pr_min: 10,
        pattern: "linear",
        seed: 123,
        peakiness: 1.0,
        question: "Explain quantum entanglement in simple terms.",
        max_output_tokens: 512,
        context_window: 2048,
        clusters: [
            {
                name: "us-east-1",
                ip: "127.0.0.1",
                port: "8040",
                gpio_list:"",
                simulated_country_code: "us-usa",
                llama_service_port: "8083"
            },
            {
                name: "us-west-2",
                ip: "127.0.0.1",
                port: "8041",
                gpio_list:"",
                simulated_country_code: "us-usa",
                llama_service_port: "8084"
            }
        ],
        global_ip: "127.0.0.1",
        global_ports: "8000",
        strato_ip: "192.168.1.50",
        strato_ports: "5000"
    },
    {
        // Example 2: High Traffic Stress Test
        id: "EXP-002",
        name: "Stress-Test-Peak-Hours",
        startdate: "2024-12-05T20:00",
        dur_days: 0,
        dur_hours: 0,
        dur_minutes: 45,
        gco2: 0.9,
        cost: 150,
        timeout_s: 30,
        turn_off_s: 60,
        max_latency: 20,
        request_pr_min: 500,
        pattern: "bursty",
        seed: 999,
        peakiness: 2.5,
        question: "Batch process 1000 summaries.",
        max_output_tokens: 128,
        context_window: 1024,
        clusters: [
            {
                name: "dk",
                ip: "127.0.0.1",
                port: "8040",
                gpio_list:"dewf",
                simulated_country_code: "dk-dk1",
                llama_service_port: "8083"
            }
        ],
        global_ip: "10.0.0.1",
        global_ports: "443",
        strato_ip: "10.0.0.25",
        strato_ports: "9090"
    },
    {
        // Example 3: Long Duration / Green Energy Focus
        id: "EXP-003",
        name: "Eco-Friendly-Long-Run",
        startdate: "2025-01-10T02:00",
        dur_days: 7,
        dur_hours: 0,
        dur_minutes: 0,
        gco2: 0.1, // Very low carbon priority
        cost: 5,
        timeout_s: 1200,
        turn_off_s: 3600,
        max_latency: 5000, // Willing to wait longer for green energy
        request_pr_min: 1,
        pattern: "sinusoidal",
        seed: 42,
        peakiness: 0.5,
        question: "Analyze climate data trends.",
        max_output_tokens: 2048,
        context_window: 8192,
        clusters: [
            {
                name: "us-east-1",
                ip: "127.0.0.1",
                port: "8040",
                gpio_list:"ewwfg",
                simulated_country_code: "us-usa",
                llama_service_port: "8083"
            },
            {
                name: "us-west-2",
                ip: "127.0.0.1",
                port: "8041",
                gpio_list:"123",
                simulated_country_code: "us-usa",
                llama_service_port: "8084"
            },
            {
                name: "dk",
                ip: "127.0.0.1",
                port: "8040",
                gpio_list:"dew",
                simulated_country_code: "dk-dk1",
                llama_service_port: "8083"
            }
        ],
        global_ip: "172.16.0.1",
        global_ports: "80",
        strato_ip: "172.16.0.10",
        strato_ports: "3000"
    }
];
export default earlierExpIds