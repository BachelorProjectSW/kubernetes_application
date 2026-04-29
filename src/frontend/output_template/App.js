import React, { useState } from "react";
import "./App.css";
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell
} from "recharts";

const COLORS = ["#3b82f6", "#22c55e", "#f59e0b"];

function App() {
  const [data, setData] = useState(null);
  const [configId, setConfigId] = useState("");

  const fetchData = async () => {
    if (!configId) return;
    const res = await fetch(`http://100.109.95.2:8015/test_results?config_id=${configId}`);
    const json = await res.json();
    setData(json);
  };

  const formatTime = (ts) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  if (!data) {
    return (
      <div className="container">
        <h1>Test Dashboard</h1>
        <div className="inputBox">
          <input
            placeholder="Enter config_id"
            value={configId}
            onChange={(e) => setConfigId(e.target.value)}
          />
          <button onClick={fetchData}>Load</button>
        </div>
      </div>
    );
  }

  // 🔹 Cluster Pie
  const clusterPie = Object.entries(data.cluster_distribution).map(
    ([key, value]) => ({ name: key, value })
  );

  // 🔹 Request Over Time
  const requestData = data.request_over_time.map((r) => ({
    timestamp: r.timestamp,
    latency: r.latency_ms,
    answer: r.answer,
    cluster: r.cluster,
    node: r.node,
    status: r.response_status_code
  }));

  // 🔹 Worker Nodes Logic
  const groupedNodes = {};
  let allTimestamps = [];

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

  // Calculate X-Axis range for the timeline
  const minTime = Math.min(...allTimestamps);
  const maxTime = Math.max(...allTimestamps);

  // Sort timestamps for each node
  Object.values(groupedNodes).forEach(cluster => {
    Object.values(cluster).forEach(nodeEvents => {
      nodeEvents.sort((a, b) => a.timestamp - b.timestamp);
    });
  });

  return (
    <div className="container">
      <h1>Test Results Dashboard</h1>

      {/* 🔹 METRICS */}
      <div className="grid">
        <Box title="Total Requests" value={data.request_count} />
        <Box title="Success Rate" value={`${data.success_rate_pct}%`} />
        <Box title="Failed" value={data.failed_requests} />
        <Box title="Avg Latency" value={`${data.avg_latency_ms.toFixed(0)} ms`} />
        <Box title="gCO2" value={`${data.total_gco2_g} g`} />
        <Box title="Cost" value={`€${data.total_cost_eur}`} />
        <Box title="Renewable" value={`${data.avg_renewable_pct}%`} />
      </div>

      {/* 🔹 REQUEST OVER TIME */}
      <ChartCard title="Requests Over Time (Latency)">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={requestData}>
            <XAxis dataKey="timestamp" tickFormatter={formatTime} />
            <YAxis />
            <Tooltip
              formatter={(value, name, props) => {
                const p = props.payload;
                return [
                  `${p.latency} ms`,
                  `Cluster: ${p.cluster} | Node: ${p.node}\n${p.answer?.slice(0, 120)}...`
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
                const isSuccess = payload.status === 200;
                return (
                  <circle cx={cx} cy={cy} r={5} fill={isSuccess ? "#22c55e" : "#ef4444"} />
                );
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* 🔹 GCO2 */}
      <ChartCard title="gCO2 Over Time">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.gco2_over_time}>
            <XAxis dataKey="timestamp" tickFormatter={formatTime} />
            <YAxis />
            <Tooltip formatter={(v) => `${v} g`} />
            <Line dataKey="cumulative_gco2_g" stroke="#22c55e" />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* 🔹 COST OVER TIME */}
      <ChartCard title="Cost Over Time">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.cost_over_time}>
            <XAxis dataKey="timestamp" tickFormatter={formatTime} />
            <YAxis />
            <Tooltip formatter={(v) => `€${v}`} />
            <Line dataKey="cumulative_cost_eur" stroke="#f59e0b" />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* 🔹 CLUSTER PIE */}
      <ChartCard title="Cluster Distribution">
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

      {/* 🔹 SERVICE TIME */}
      <ChartCard title="Service Timeout Breakdown">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.service_timeout_over_time}>
            <XAxis dataKey="timestamp" tickFormatter={formatTime} />
            <YAxis />
            <Tooltip />
            <Line dataKey="global_choose_cluster" stroke="#3b82f6" />
            <Line dataKey="cluster_queue_time_ms" stroke="#f59e0b" />
            <Line dataKey="llama_inference_ms" stroke="#22c55e" />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* 🔹 UPDATED: WORKER NODES WITH TIMESTAMPS */}
      <ChartCard title="Worker Node Status Timeline">
        {Object.entries(groupedNodes).map(([cluster, nodes]) => (
          <div key={cluster} className="clusterBlock">
            <h4 className="clusterTitle">{cluster.toUpperCase()} Cluster</h4>
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
            {/* Shared Timestamp Axis for the Cluster */}
            <div className="timestampAxis">
              <span>{formatTime(minTime)}</span>
              <span>{formatTime((minTime + maxTime) / 2)}</span>
              <span>{formatTime(maxTime)}</span>
            </div>
          </div>
        ))}
      </ChartCard>
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