function Latency({ inputs, handleChange }) {
  return (
    <div className="section-panel">
      <div className="panel-title">
        ⚡ Latency
      </div>

      <div className="field-group">
        <label>Latency Window</label>
        <input
          type="number"
          name="latency_window"
          value={inputs.latency_window}
          onChange={handleChange}
        />
      </div>

      <div className="field-group">
        <label>Max Latency (ms)</label>
        <input
          type="number"
          name="max_latency"
          value={inputs.max_latency}
          onChange={handleChange}
        />
      </div>
    </div>
  );
}
export default Latency;
