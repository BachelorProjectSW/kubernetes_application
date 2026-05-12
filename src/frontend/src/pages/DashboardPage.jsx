import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import "./App.css";

const COLORS = ["#3b82f6", "#22c55e", "#f59e0b"];

function DashboardPage() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [configId, setConfigId] = useState("");
  const [configs, setConfigs] = useState([]);
  const [loadingConfigs, setLoadingConfigs] = useState(false);
  const [compareConfigId, setCompareConfigId] = useState("");
  const [compareData, setCompareData] = useState(null);

  const getExperimentName = (config) =>
    config.config_name ||
    config.config_json?.name ||
    config.test_name ||
    "Unnamed experiment";

  useEffect(() => {
    const fetchConfigs = async () => {
      setLoadingConfigs(true);

      try {
        const res = await fetch("http://100.109.95.2:8099/get_configs");

        if (!res.ok) {
          throw new Error("Failed to fetch configs");
        }

        const json = await res.json();
        setConfigs(json);
      } catch (err) {
        console.error("Error fetching configs:", err);
      } finally {
        setLoadingConfigs(false);
      }
    };

    fetchConfigs();
  }, []);

  const fetchOneConfig = async (id) => {
    const res = await fetch(
      `http://100.109.95.2:8015/test_results?config_id=${encodeURIComponent(id)}`,
    );

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Failed to fetch test results: ${res.status} ${text}`);
    }

    return res.json();
  };

  useEffect(() => {
    const configIdFromUrl = searchParams.get("config_id");

    if (!configIdFromUrl) return;

    const loadConfigFromUrl = async () => {
      try {
        setConfigId(configIdFromUrl);

        const json = await fetchOneConfig(configIdFromUrl);
        setData(json);

        setCompareConfigId("");
        setCompareData(null);
      } catch (err) {
        console.error("Error loading config from URL:", err);
        alert(String(err));
      }
    };

    loadConfigFromUrl();
  }, [searchParams]);

  const fetchData = async () => {
    if (!configId) return;

    try {
      const json = await fetchOneConfig(configId);
      setData(json);

      //Reset old comparison when primary config changes
      setCompareConfigId("");
      setCompareData(null);
    } catch (err) {
      console.error(err);
      alert(String(err));
    }
  };

  const fetchCompareData = async () => {
    if (!compareConfigId) return;

    try {
      const json = await fetchOneConfig(compareConfigId);
      setCompareData(json);
    } catch (err) {
      console.error(err);
      alert(String(err));
    }
  };

  const formatTime = (ts) =>
    new Date(ts).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });

  const requestData = data
    ? data.request_over_time.map((r) => ({
        timestamp: r.timestamp,
        latency: r.latency_ms,
        answer: r.answer,
        cluster: r.cluster,
        node: r.node,
        status: r.response_status_code,
        success: r.ok,
      }))
    : [];

  const mergeByIndex = (
    primaryArray = [],
    compareArray = [],
    primaryKey,
    compareKey,
    valueSelector,
  ) => {
    const maxLength = Math.max(primaryArray.length, compareArray.length);

    return Array.from({ length: maxLength }, (_, index) => ({
      index: index + 1,
      [primaryKey]: primaryArray[index]
        ? valueSelector(primaryArray[index])
        : null,
      [compareKey]: compareArray[index]
        ? valueSelector(compareArray[index])
        : null,
      primaryTimestamp: primaryArray[index]?.timestamp,
      compareTimestamp: compareArray[index]?.timestamp,
    }));
  };

  const latencyComparisonData =
    data && compareData
      ? mergeByIndex(
          data.request_over_time,
          compareData.request_over_time,
          "primaryLatency",
          "compareLatency",
          (r) => r.latency_ms,
        ).map((point, index) => {
          const primary = data.request_over_time[index];
          const comparison = compareData.request_over_time[index];

          return {
            ...point,

            primaryCluster: primary?.cluster,
            primaryAnswer: primary?.answer,

            compareCluster: comparison?.cluster,
            compareAnswer: comparison?.answer,
          };
        })
      : [];

  const gco2ComparisonData =
    data && compareData
      ? mergeByIndex(
          data.gco2_over_time,
          compareData.gco2_over_time,
          "primaryGco2",
          "compareGco2",
          (r) => r.cumulative_gco2_g,
        )
      : [];

  const costComparisonData =
    data && compareData
      ? mergeByIndex(
          data.cost_over_time,
          compareData.cost_over_time,
          "primaryCost",
          "compareCost",
          (r) => r.cumulative_cost_eur,
        )
      : [];

  const getRunTimeRange = (run) => {
    if (!run) return { startMs: Date.now(), endMs: Date.now() };

    const timestamps = [
      ...(run.request_over_time || []).map((r) =>
        new Date(r.timestamp).getTime(),
      ),
      ...(run.node_status_over_time || []).map((r) =>
        new Date(r.timestamp).getTime(),
      ),
    ].filter(Boolean);

    if (timestamps.length === 0) {
      return { startMs: Date.now(), endMs: Date.now() };
    }

    return {
      startMs: Math.min(...timestamps),
      endMs: Math.max(...timestamps),
    };
  };

  const primaryRange = getRunTimeRange(data);
  const compareRange = getRunTimeRange(compareData);
  // Worker node timeline data
  const buildGroupedNodes = (run) => {
    const grouped = {};
    const timestamps = [];

    if (!run) {
      return { grouped, timestamps };
    }

    (run.node_status_over_time || []).forEach((entry) => {
      const { cluster, node, status, timestamp } = entry;

      const ts = new Date(timestamp).getTime();
      timestamps.push(ts);

      if (!grouped[cluster]) grouped[cluster] = {};
      if (!grouped[cluster][node]) grouped[cluster][node] = [];

      grouped[cluster][node].push({
        status,
        timestamp: ts,
        timeStr: formatTime(timestamp),
      });
    });

    Object.values(grouped).forEach((cluster) => {
      Object.values(cluster).forEach((nodeEvents) => {
        nodeEvents.sort((a, b) => a.timestamp - b.timestamp);
      });
    });

    return { grouped, timestamps };
  };

  const primaryNodes = buildGroupedNodes(data);
  const compareNodes = buildGroupedNodes(compareData);

  const allNodeTimestamps = [
    ...primaryNodes.timestamps,
    ...compareNodes.timestamps,
  ];

  const minTime = allNodeTimestamps.length
    ? Math.min(...allNodeTimestamps)
    : Date.now();

  const maxTime = allNodeTimestamps.length
    ? Math.max(...allNodeTimestamps)
    : Date.now();

  return (
    <div className="container">
      <h1>Test Results Dashboard</h1>

      {/* ALWAYS VISIBLE INPUT */}
      <div className="inputBox">
        <select
          value={configId}
          onChange={(e) => setConfigId(e.target.value)}
          disabled={loadingConfigs}
        >
          <option value="">
            {loadingConfigs ? "Loading experiments..." : "Select experiment"}
          </option>

          {configs.map((config) => (
            <option key={config.config_id} value={config.config_id}>
              {getExperimentName(config)}
            </option>
          ))}
        </select>

        <button type="submit" onClick={fetchData} disabled={!configId}>
          Load
        </button>
      </div>

      {/* NO DATA */}
      {!data ? (
        <div className="emptyState">
          <p>Select an Experiment and press Load.</p>
        </div>
      ) : (
        <>
          {/* OPTIONAL COMPARISON INPUT */}
          <div className="inputBox compareBox">
            <div>
              <h3>Compare with another test run</h3>
            </div>

            <select
              value={compareConfigId}
              onChange={(e) => setCompareConfigId(e.target.value)}
              disabled={loadingConfigs}
            >
              <option value="">Select optional comparison experiment</option>

              {configs
                .filter((config) => config.config_id !== configId)
                .map((config) => (
                  <option key={config.config_id} value={config.config_id}>
                    {getExperimentName(config)}
                  </option>
                ))}
            </select>

            <button
              type="submit"
              onClick={fetchCompareData}
              disabled={!compareConfigId}
            >
              Compare
            </button>
          </div>
          <MetricsGrid title={`Primary Run: ${data.test_name}`} run={data} />

          {compareData && (
            <MetricsGrid
              title={`Compared Run: ${compareData.test_name}`}
              run={compareData}
            />
          )}

          {/* REQUEST OVER TIME */}
          <ChartCard
            title={
              compareData
                ? "Latency Comparison"
                : "Requests Over Time (Latency)"
            }
          >
            <ResponsiveContainer width="100%" height={300}>
              <LineChart
                data={compareData ? latencyComparisonData : requestData}
              >
                <XAxis
                  dataKey={compareData ? "index" : "timestamp"}
                  tickFormatter={compareData ? undefined : formatTime}
                  label={
                    compareData
                      ? {
                          value: "Request #",
                          position: "insideBottom",
                          offset: -5,
                        }
                      : undefined
                  }
                />

                <YAxis />

                <Tooltip
                  content={(props) =>
                    compareData ? (
                      <div className="customTooltip">
                        <p>
                          <strong>Request #{props.label}</strong>
                        </p>

                        {props.payload?.map((entry) => {
                          const point = entry.payload;
                          const isPrimary = entry.dataKey === "primaryLatency";

                          return (
                            <div key={entry.dataKey}>
                              <p>
                                <strong>
                                  {isPrimary
                                    ? `Primary: ${data.test_name}`
                                    : `Comparison: ${compareData.test_name}`}
                                </strong>
                              </p>

                              <p>
                                <strong>Cluster:</strong>{" "}
                                {isPrimary
                                  ? (point.primaryCluster ?? "N/A")
                                  : (point.compareCluster ?? "N/A")}
                              </p>

                              <p>
                                <strong>Answer:</strong>{" "}
                                {isPrimary
                                  ? (point.primaryAnswer ?? "N/A")
                                  : (point.compareAnswer ?? "N/A")}
                              </p>

                              <p>
                                <strong>Latency:</strong> {entry.value ?? "N/A"}{" "}
                                ms
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <LatencyTooltip {...props} formatTime={formatTime} />
                    )
                  }
                />
                {compareData ? (
                  <>
                    <Line
                      type="monotone"
                      dataKey="primaryLatency"
                      name="Primary"
                      stroke="#a855f7"
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                      strokeWidth={2}
                      connectNulls
                    />

                    <Line
                      type="monotone"
                      dataKey="compareLatency"
                      name="Comparison"
                      stroke="#22c55e"
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                      strokeWidth={2}
                      connectNulls
                    />
                  </>
                ) : (
                  <Line type="monotone" dataKey="latency" stroke="#a855f7" />
                )}
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* GCO2 */}
          <ChartCard title={compareData ? "gCO2 Comparison" : "gCO2 Over Time"}>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart
                data={compareData ? gco2ComparisonData : data.gco2_over_time}
              >
                <XAxis
                  dataKey={compareData ? "index" : "timestamp"}
                  tickFormatter={compareData ? undefined : formatTime}
                  label={
                    compareData
                      ? {
                          value: "Point #",
                          position: "insideBottom",
                          offset: -5,
                        }
                      : undefined
                  }
                />

                <YAxis />

                <Tooltip
                  formatter={(value, name) => {
                    if (compareData) {
                      return [
                        `${value} g`,
                        name === "primaryGco2"
                          ? `Primary: ${data.test_name}`
                          : `Comparison: ${compareData.test_name}`,
                      ];
                    }

                    return [`${value} g`, "Cumulative gCO2"];
                  }}
                  labelFormatter={(label) =>
                    compareData ? `Point #${label}` : formatTime(label)
                  }
                />

                {compareData ? (
                  <>
                    <Line
                      type="monotone"
                      dataKey="primaryGco2"
                      name="Primary"
                      stroke="#3b82f6"
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                      strokeWidth={2}
                      connectNulls
                    />

                    <Line
                      type="monotone"
                      dataKey="compareGco2"
                      name="Comparison"
                      stroke="#f59e0b"
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                      strokeWidth={2}
                      connectNulls
                    />
                  </>
                ) : (
                  <Line dataKey="cumulative_gco2_g" stroke="#22c55e" />
                )}
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* COST OVER TIME */}
          <ChartCard title={compareData ? "Cost Comparison" : "Cost Over Time"}>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart
                data={compareData ? costComparisonData : data.cost_over_time}
              >
                <XAxis
                  dataKey={compareData ? "index" : "timestamp"}
                  tickFormatter={compareData ? undefined : formatTime}
                  label={
                    compareData
                      ? {
                          value: "Point #",
                          position: "insideBottom",
                          offset: -5,
                        }
                      : undefined
                  }
                />

                <YAxis />

                <Tooltip
                  formatter={(value, name) => {
                    if (compareData) {
                      return [
                        `€${value}`,
                        name === "primaryCost"
                          ? `Primary: ${data.test_name}`
                          : `Comparison: ${compareData.test_name}`,
                      ];
                    }

                    return [`€${value}`, "Cumulative Cost"];
                  }}
                  labelFormatter={(label) =>
                    compareData ? `Point #${label}` : formatTime(label)
                  }
                />

                {compareData ? (
                  <>
                    <Line
                      type="monotone"
                      dataKey="primaryCost"
                      name="Primary"
                      stroke="#3b82f6"
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                      strokeWidth={2}
                      connectNulls
                    />

                    <Line
                      type="monotone"
                      dataKey="compareCost"
                      name="Comparison"
                      stroke="#f59e0b"
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                      strokeWidth={2}
                      connectNulls
                    />
                  </>
                ) : (
                  <Line dataKey="cumulative_cost_eur" stroke="#f59e0b" />
                )}
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* CLUSTER PIE */}
          <div className={compareData ? "pairedCharts" : ""}>
            <ClusterDistributionChart
              title={`Primary Run — Cluster Distribution`}
              run={data}
            />

            {compareData && (
              <ClusterDistributionChart
                title={`Compared Run — Cluster Distribution`}
                run={compareData}
              />
            )}
          </div>

          {/* SERVICE TIME */}
          <ServiceTimeoutChart
            title="Primary Run — Service Timeout Breakdown"
            run={data}
            formatTime={formatTime}
          />

          {compareData && (
            <ServiceTimeoutChart
              title="Compared Run — Service Timeout Breakdown"
              run={compareData}
              formatTime={formatTime}
            />
          )}

          {/* WORKER NODE STATUS */}
          <WorkerNodeStatusComparison
            primaryNodes={primaryNodes}
            compareNodes={compareNodes}
            compareData={compareData}
            primaryRange={primaryRange}
            compareRange={compareRange}
          />
        </>
      )}
    </div>
  );
}

const MetricsGrid = ({ title, run }) => (
  <section className="runSection">
    <h2>{title}</h2>

    <div className="grid">
      <Box title="Total Requests" value={run.request_count} />
      <Box title="Success Rate" value={`${run.success_rate_pct}%`} />
      <Box title="Failed" value={run.failed_requests} />
      <Box title="Avg Latency" value={`${run.avg_latency_ms.toFixed(0)} ms`} />
      <Box title="gCO2" value={`${run.total_gco2_g} g`} />
      <Box title="Cost" value={`€${run.total_cost_eur}`} />
      <Box title="Renewable" value={`${run.avg_renewable_pct}%`} />
    </div>
  </section>
);
const ClusterDistributionChart = ({ title, run }) => {
  const clusterPie = Object.entries(run.cluster_distribution || {}).map(
    ([key, value]) => ({
      name: key,
      value,
    }),
  );

  return (
    <ChartCard title={title}>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie data={clusterPie} dataKey="value" nameKey="name">
            {clusterPie.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>

          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
};

const ServiceTimeoutChart = ({ title, run, formatTime }) => (
  <ChartCard title={title}>
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={run.service_timeout_over_time || []}>
        <XAxis dataKey="timestamp" tickFormatter={formatTime} />

        <YAxis />

        <Tooltip />

        <Line
          dataKey="global_choose_cluster"
          name="Choose Cluster"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={{ r: 3 }}
          activeDot={{ r: 5 }}
        />

        <Line
          dataKey="cluster_queue_time_ms"
          name="Queue Time"
          stroke="#f59e0b"
          strokeWidth={2}
          dot={{ r: 3 }}
          activeDot={{ r: 5 }}
        />

        <Line
          dataKey="llama_inference_ms"
          name="Llama Inference"
          stroke="#22c55e"
          strokeWidth={2}
          dot={{ r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  </ChartCard>
);

const NodeTimelineRows = ({ label, nodes, rangeMs }) => {
  const durationMs = Math.max(rangeMs.endMs - rangeMs.startMs, 1);
  const durationSeconds = Math.round(durationMs / 1000);

  return (
    <div className="nodeRunBlock">
      <h5>
        {label} <span className="durationLabel">0s → {durationSeconds}s</span>
      </h5>

      {Object.entries(nodes).map(([node, states]) => {
        const sortedStates = [...states].sort(
          (a, b) => a.timestamp - b.timestamp,
        );

        const mergedStates = sortedStates.reduce((acc, state) => {
          const last = acc[acc.length - 1];

          if (last && last.status === state.status) {
            return acc;
          }

          acc.push(state);
          return acc;
        }, []);

        return (
          <div key={node} className="nodeRowContainer">
            <div className="nodeRow">
              <div className="nodeInfo">
                <span className="nodeLabel">{node}</span>
              </div>

              <div
                className="relativeTimeline"
                title={`${node} — no status data before first event`}
              >
                {mergedStates.map((state, index) => {
                  const currentMs = state.timestamp;
                  const nextMs =
                    mergedStates[index + 1]?.timestamp ?? rangeMs.endMs;

                  const leftPct =
                    ((currentMs - rangeMs.startMs) / durationMs) * 100;

                  const widthPct = ((nextMs - currentMs) / durationMs) * 100;

                  return (
                    <div
                      key={index}
                      className={`relativeTimelineBlock ${state.status}`}
                      style={{
                        left: `${Math.max(0, leftPct)}%`,
                        width: `${Math.max(0.5, widthPct)}%`,
                      }}
                      title={`${node} — ${state.status} — ${Math.round(
                        (currentMs - rangeMs.startMs) / 1000,
                      )}s to ${Math.round((nextMs - rangeMs.startMs) / 1000)}s`}
                    />
                  );
                })}
              </div>
            </div>
          </div>
        );
      })}

      <div className="relativeTimestampAxis">
        <span>0s</span>
        <span>{Math.round(durationSeconds / 2)}s</span>
        <span>{durationSeconds}s</span>
      </div>
    </div>
  );
};

const WorkerNodeStatusComparison = ({
  primaryNodes,
  compareNodes,
  compareData,
  primaryRange,
  compareRange,
}) => {
  const clusters = Array.from(
    new Set([
      ...Object.keys(primaryNodes.grouped),
      ...Object.keys(compareNodes.grouped),
    ]),
  );

  if (clusters.length === 0) {
    return (
      <ChartCard title="Worker Node Status Timeline">
        <p>No node status logs found for this run.</p>
      </ChartCard>
    );
  }

  return (
    <ChartCard title="Worker Node Status Timeline">
      {clusters.map((cluster) => (
        <div key={cluster} className="clusterCompareBlock">
          <h4 className="clusterTitle">{cluster.toUpperCase()}</h4>

          <NodeTimelineRows
            label="Primary"
            nodes={primaryNodes.grouped[cluster] || {}}
            rangeMs={primaryRange}
          />

          {compareData && (
            <NodeTimelineRows
              label="Comparison"
              nodes={compareNodes.grouped[cluster] || {}}
              rangeMs={compareRange}
            />
          )}
        </div>
      ))}
    </ChartCard>
  );
};

const LatencyTooltip = ({ active, payload, label, formatTime }) => {
  if (!active || !payload || payload.length === 0) return null;

  const point = payload[0].payload;

  return (
    <div className="customTooltip">
      <p>
        <strong>{formatTime(label)}</strong>
      </p>
      <p>
        <strong>Cluster:</strong> {point.cluster ?? "N/A"}
      </p>
      <p>
        <strong>Answer:</strong> {point.answer ?? "N/A"}
      </p>
      <p>
        <strong>Latency:</strong> {point.latency ?? "N/A"} ms
      </p>
    </div>
  );
};

const Box = ({ title, value }) => (
  <div className="box">
    <h4>{title}</h4>
    <p>{value}</p>
  </div>
);

const ChartCard = ({ title, children }) => (
  <div className="chart">
    <h3>{title}</h3>
    {children}
  </div>
);

export default DashboardPage;
