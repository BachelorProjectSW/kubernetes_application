import { useEffect, useState } from "react";
const CONFIG_API_URL = import.meta.env.VITE_CONFIG_API_URL;

function Ids({ inputs, setInputs, handleChange }) {
  const [earlierConfigs, setEarlierConfigs] = useState([]);
  const [isExisting, setIsExisting] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchConfigs = async () => {
      setLoading(true);

      try {
        const response = await fetch(`${CONFIG_API_URL}/get_configs`);

        if (!response.ok) {
          throw new Error("Failed to fetch configs");
        }

        const data = await response.json();
        setEarlierConfigs(data);
      } catch (err) {
        console.error("Error fetching historical data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchConfigs();
  }, []);

  const getExperimentName = (entry) =>
    entry.config_name || entry.config_json?.name || entry.config_id || "";

  const toggleMode = () => {
    setIsExisting((current) => !current);

    setInputs((values) => ({
      ...values,
      expID: null,
      name: "",
    }));
  };

  const handleSelectHistory = (e) => {
    const selectedName = e.target.value;

    if (!selectedName) {
      setInputs((values) => ({
        ...values,
        expID: null,
        name: "",
      }));
      return;
    }

    const entry = earlierConfigs.find(
      (config) => getExperimentName(config) === selectedName,
    );

    if (!entry?.config_json) {
      setInputs((values) => ({
        ...values,
        expID: null,
        name: selectedName,
      }));
      return;
    }

    const config = entry.config_json;

    let formattedDate = "";

    if (config.start?.start_time_simulated) {
      const [datePart, timePart] = config.start.start_time_simulated.split(" ");
      const [day, month, year] = datePart.split("/");
      const [hours, minutes] = timePart.split(":");

      formattedDate = `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    const totalSeconds = config.start?.duration_time_s || 0;
    const d = Math.floor(totalSeconds / 86400);
    const h = Math.floor((totalSeconds % 86400) / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);

    setInputs({
      expID: null,
      name: getExperimentName(entry),

      startdate: formattedDate,
      dur_days: d,
      dur_hours: h,
      dur_minutes: m,

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
      port_strato: config.strato?.port ?? "",
    });
  };

  const handleNewExperimentName = (e) => {
    setInputs((values) => ({
      ...values,
      expID: null,
      name: e.target.value,
    }));
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
        <span
          style={{
            fontSize: "0.68rem",
            color: "var(--text-label)",
            letterSpacing: "0.04em",
          }}
        >
          Experiment Name
        </span>

        <button
          type="button"
          onClick={toggleMode}
          style={{
            fontSize: "0.65rem",
            padding: "0.15rem 0.5rem",
          }}
        >
          {isExisting ? "↩ New Experiment" : "📂 Load Existing"}
        </button>

        {loading && (
          <span
            style={{
              fontSize: "0.65rem",
              color: "var(--text-muted)",
              fontStyle: "italic",
            }}
          >
            fetching…
          </span>
        )}
      </div>

      {isExisting ? (
        <select
          name="name"
          value={inputs.name || ""}
          onChange={handleSelectHistory}
          style={{ minWidth: "320px" }}
        >
          <option value="">— Select an experiment —</option>

          {earlierConfigs.map((config) => {
            const experimentName = getExperimentName(config);

            return (
              <option
                key={config.config_id || experimentName}
                value={experimentName}
              >
                {experimentName}
              </option>
            );
          })}
        </select>
      ) : (
        <input
          type="text"
          name="name"
          value={inputs.name || ""}
          onChange={handleNewExperimentName}
          placeholder="e.g. baseline-run-01"
          style={{ minWidth: "320px" }}
        />
      )}
    </div>
  );
}

export default Ids;
