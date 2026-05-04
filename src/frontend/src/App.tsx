import AllConfigs from "./components/play_around";
import { handleSubmit } from "./components/submitData";

function App() {
  return (
    <div style={{ maxWidth: "960px", margin: "0 auto", padding: "0 2rem" }}>
      <div className="page-header">
        <div className="page-header-icon">⚡</div>
        <div>
          <h1>Microgrid <span>Config</span></h1>
          <div className="page-subtitle">Experiment Configuration System</div>
        </div>
      </div>

      <div className="status-bar">
        <div className="status-dot" />
        <span>SYSTEM READY</span>
        <span style={{ marginLeft: "auto", opacity: 0.5 }}>
          {new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}
        </span>
      </div>

      <AllConfigs onSubmit={handleSubmit} />
    </div>
  );
}

export default App;
