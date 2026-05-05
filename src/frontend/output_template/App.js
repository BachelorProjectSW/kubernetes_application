import React, { useState } from "react";
import "./App.css";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from "recharts";

const COLORS = ["#3b82f6", "#22c55e", "#f59e0b"];

function App() {
  const [data, setData] = useState(null);
  const [configId, setConfigId] = useState("");

  const fetchData = async () => {
    if (!configId) return;

    try {
      const res = await fetch(
        `http://100.109.95.2:8099/test_results?config_id=${configId}`
      );

      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error(err);
    }
  };

  const formatTime = (ts) =>
    new Date(ts).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });

  // Only calculate these when data exists
  const clusterPie = data
    ? Object.entries(data.cluster_distribution).map(([key, value]) => ({
        name: key,
        value
      }))
    : [];

  const requestData = data
    ? data.request_over_time.map((r) => ({
        timestamp: r.timestamp,
        latency: r.latency_ms,
        answer: r.answer,
        cluster: r.cluster,
        node: r.node,
        status: r.response_status_code,
        ok: r.ok
      }))
    : [];

  const sentRawData = data ? (data.sent_over_time || []) : [];
  const sentStartMs = data?.started_at
    ? new Date(data.started_at).getTime()
    : sentRawData.length
      ? new Date(sentRawData[0].timestamp).getTime()
      : Date.now();
  const sentEndMs = data?.ended_at
    ? new Date(data.ended_at).getTime()
    : sentRawData.length
      ? new Date(sentRawData[sentRawData.length - 1].timestamp).getTime()
      : sentStartMs;

  const sentDurationS = Math.max(1, Math.floor((sentEndMs - sentStartMs) / 1000));

  // Dynamic bucketing for readability:
  // - Always at least 60s buckets.
  // - For longer tests, increase bucket size to keep point count manageable.
  const targetPoints = 80;
  const dynamicBucketS = Math.max(60, Math.ceil(sentDurationS / targetPoints));
  const sentBucketS = Math.ceil(dynamicBucketS / 60) * 60;

  const sentBuckets = sentRawData.reduce((acc, s) => {
    const tsMs = new Date(s.timestamp).getTime();
    const elapsedS = Math.max(0, Math.floor((tsMs - sentStartMs) / 1000));
    const bucketStartS = Math.floor(elapsedS / sentBucketS) * sentBucketS;
    acc[bucketStartS] = (acc[bucketStartS] || 0) + 1;
    return acc;
  }, {});

  const sentData = Object.entries(sentBuckets)
    .map(([elapsedS, count]) => ({
      elapsed_s: Number(elapsedS),
      sent_count: count
    }))
    .sort((a, b) => a.elapsed_s - b.elapsed_s);

  // Worker node timeline data
  const groupedNodes = {};
  let allTimestamps = [];

  if (data) {
    data.node_status_over_time.forEach((entry) => {
      const { cluster, node, status, timestamp } = entry;

      const ts = new Date(timestamp).getTime();
      allTimestamps.push(ts);

      if (!groupedNodes[cluster]) groupedNodes[cluster] = {};
      if (!groupedNodes[cluster][node]) groupedNodes[cluster][node] = [];

      groupedNodes[cluster][node].push({
        status,
        timestamp: ts,
        timeStr: formatTime(timestamp)
      });
    });

    Object.values(groupedNodes).forEach((cluster) => {
      Object.values(cluster).forEach((nodeEvents) => {
        nodeEvents.sort((a, b) => a.timestamp - b.timestamp);
      });
    });
  }

  const minTime = allTimestamps.length
    ? Math.min(...allTimestamps)
    : Date.now();

  const maxTime = allTimestamps.length
    ? Math.max(...allTimestamps)
    : Date.now();

  return (
    <div className="container">
      <h1>Test Results Dashboard</h1>

      {/* ALWAYS VISIBLE INPUT */}
      <div className="inputBox">
        <input
          placeholder="Enter config_id"
          value={configId}
          onChange={(e) => setConfigId(e.target.value)}
        />

        <button onClick={fetchData}>Load</button>
      </div>

      {/* NO DATA */}
      {!data ? (
        <div className="emptyState">
          <p>Enter a config_id and press Load.</p>
        </div>
      ) : (
        <>
          {/* METRICS */}
          <div className="grid">
            <Box title="Total Requests" value={data.request_count} />

            <Box
              title="Success Rate"
              value={`${data.success_rate_pct}%`}
            />

            <Box title="Failed" value={data.failed_requests} />

            <Box
              title="Avg Latency"
              value={`${data.avg_latency_ms.toFixed(0)} ms`}
            />

            <Box
              title="gCO2"
              value={`${data.total_gco2_g} g`}
            />

            <Box
              title="Cost"
              value={`€${data.total_cost_eur}`}
            />

            <Box
              title="Renewable"
              value={`${data.avg_renewable_pct}%`}
            />
          </div>

          {/* SENT OVER TIME */}
          <ChartCard title="Sent Over Time">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={sentData}>
                <XAxis
                  dataKey="elapsed_s"
                  tickFormatter={(v) => `${v}s`}
                  label={{ value: "Elapsed time (s)", position: "insideBottom", offset: -5 }}
                />

                <YAxis
                  allowDecimals={false}
                  label={{ value: "Sent count", angle: -90, position: "insideLeft" }}
                />

                <Tooltip
                  labelFormatter={(label) => `t+${label}s`}
                  formatter={(value) => [value, `Sent in ${sentBucketS}s bucket`]}
                />

                <Line
                  type="stepAfter"
                  dataKey="sent_count"
                  stroke="#3b82f6"
                  dot={{ r: 4, fill: "#3b82f6" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* REQUEST OVER TIME */}
          <ChartCard title="Requests Over Time (Latency)">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={requestData}>
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={formatTime}
                />

                <YAxis />

                <Tooltip
                  formatter={(value, name, props) => {
                    const p = props.payload;

                    return [
                      `${p.latency} ms`,
                      `Cluster: ${p.cluster} | Node: ${p.node}\n${p.answer?.slice(
                        0,
                        120
                      )}...`
                    ];
                  }}
                  labelFormatter={(label) => formatTime(label)}
                />

                <Line
                  type="monotone"
                  dataKey="latency"
                  stroke="#a855f7"
                  dot={(props) => {
                    const { cx, cy, payload } = props;

                    const isSuccess = payload.ok === true;

                    return (
                      <circle
                        cx={cx}
                        cy={cy}
                        r={5}
                        fill={isSuccess ? "#22c55e" : "#ef4444"}
                      />
                    );
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* GCO2 */}
          <ChartCard title="gCO2 Over Time">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={data.gco2_over_time}>
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={formatTime}
                />

                <YAxis />

                <Tooltip formatter={(v) => `${v} g`} />

                <Line
                  dataKey="cumulative_gco2_g"
                  stroke="#22c55e"
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* COST OVER TIME */}
          <ChartCard title="Cost Over Time">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={data.cost_over_time}>
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={formatTime}
                />

                <YAxis />

                <Tooltip formatter={(v) => `€${v}`} />

                <Line
                  dataKey="cumulative_cost_eur"
                  stroke="#f59e0b"
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* CLUSTER PIE */}
          <ChartCard title="Cluster Distribution">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={clusterPie}
                  dataKey="value"
                  nameKey="name"
                >
                  {clusterPie.map((_, i) => (
                    <Cell
                      key={i}
                      fill={COLORS[i % COLORS.length]}
                    />
                  ))}
                </Pie>

                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* SERVICE TIME */}
          <ChartCard title="Service Timeout Breakdown">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={data.service_timeout_over_time}>
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={formatTime}
                />

                <YAxis />

                <Tooltip />

                <Line
                  dataKey="global_choose_cluster"
                  stroke="#3b82f6"
                />

                <Line
                  dataKey="cluster_queue_time_ms"
                  stroke="#f59e0b"
                />

                <Line
                  dataKey="llama_inference_ms"
                  stroke="#22c55e"
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* WORKER NODE STATUS */}
          <ChartCard title="Worker Node Status Timeline">
            {Object.entries(groupedNodes).map(([cluster, nodes]) => (
              <div key={cluster} className="clusterBlock">
                <h4 className="clusterTitle">
                  {cluster.toUpperCase()} Cluster
                </h4>

                {Object.entries(nodes).map(([node, states]) => (
                  <div key={node} className="nodeRowContainer">
                    <div className="nodeRow">
                      <div className="nodeInfo">
                        <span className="nodeLabel">{node}</span>
                      </div>

                      <div className="timelineContainer">
                        <div className="timeline">
                          {states.map((s, i) => (
                            <div
                              key={i}
                              className={`timelineBlock ${s.status}`}
                              title={`${s.timeStr} - State: ${s.status}`}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Shared Timestamp Axis */}
                <div className="timestampAxis">
                  <span>{formatTime(minTime)}</span>

                  <span>
                    {formatTime((minTime + maxTime) / 2)}
                  </span>

                  <span>{formatTime(maxTime)}</span>
                </div>
              </div>
            ))}
          </ChartCard>
        </>
      )}
    </div>
  );
}

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

export default App;