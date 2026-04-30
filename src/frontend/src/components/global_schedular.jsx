function GlobalScheduler({ inputs, handleChange }) {
  return (
    <div className="section-panel">
      <div className="panel-title">
        <span className="panel-title-icon">🌐</span>
        Global Scheduler
      </div>

      <div className="field-group">
        <label>IP Address</label>
        <input
          type="text"
          name="ip_global"
          value={inputs.ip_global}
          onChange={handleChange}
        />
      </div>

      <div className="field-group">
        <label>Port</label>
        <input
          type="number"
          name="port_global"
          value={inputs.port_global}
          onChange={handleChange}
        />
      </div>
    </div>
  );
}

export default GlobalScheduler;
