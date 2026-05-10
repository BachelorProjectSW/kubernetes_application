import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import AllConfigs from "./components/play_around";
import { handleSubmit } from "./components/submitData";
import DashboardPage from "./pages/DashboardPage";
import "./index.css"

function ConfigPage() {
  const [testStatus, setTestStatus] = useState("idle");
  const [statusError, setStatusError] = useState("");

  const isLocked = testStatus === "running" || testStatus === "stopping";

  const fetchTestStatus = async () => {
    try {
      const res = await fetch("http://100.109.95.2:8099/test_status");

      if (!res.ok) {
        throw new Error("Failed to fetch test status");
      }

      const json = await res.json();

      // Supports either:
      // { status: "running" }
      // or just "running"
      const status = typeof json === "string" ? json : json.status;

      setTestStatus(status ?? "idle");
      setStatusError("");
    } catch (err) {
      console.error("Error fetching test status:", err);
      setStatusError("Could not read test status");
    }
  };

  useEffect(() => {
    fetchTestStatus();
  }, []);

  useEffect(() => {
    if (!isLocked) return;

    const interval = setInterval(() => {
      fetchTestStatus();
    }, 1500);

    return () => clearInterval(interval);
  }, [isLocked]);

  const handleConfigSubmit = async (...args) => {
    try {
      // Lock immediately when user presses Start test
      setTestStatus("running");
      setStatusError("");

      await handleSubmit(...args);

      // Confirm real backend status after submit
      await fetchTestStatus();
    } catch (err) {
      console.error("Error starting test:", err);
      setStatusError("Failed to start test");
      setTestStatus("idle");
    }
  };

  return (
    <div style={{ maxWidth: "960px", margin: "0 auto", padding: "0 2rem" }}>
      <div className="page-header">
        <div className="page-header-icon">⚡</div>
        <div>
          <h1>
            Microgrid <span>Config</span>
          </h1>
          <div className="page-subtitle">Experiment Configuration System</div>
        </div>
      </div>

      <div className="status-bar">
        <div className={`status-dot ${isLocked ? "running" : ""}`} />

        <span>
          {isLocked ? `TEST ${testStatus.toUpperCase()}` : "SYSTEM READY"}
        </span>

        {statusError && <span className="status-error">{statusError}</span>}

        <span style={{ marginLeft: "auto", opacity: 0.5 }}>
          {new Date().toLocaleDateString("en-GB", {
            day: "2-digit",
            month: "short",
            year: "numeric",
          })}
        </span>
      </div>

      <div className={`config-lock-wrapper ${isLocked ? "locked" : ""}`}>
        <AllConfigs onSubmit={handleConfigSubmit} />

        {isLocked && (
          <div className="config-lock-overlay">
            <div className="loader" />
            <div className="lock-title">Test in progress</div>
            <div className="lock-subtitle">
              Waiting for the test to finish before unlocking configuration…
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
function App() {
  return (
    <BrowserRouter>
          <nav className="top-nav">
      <NavLink
        to="/"
        end
        className={({ isActive }) =>
          `nav-link ${isActive ? "active" : ""}`
        }
      >
        <span className="nav-icon">📝</span>
        <span>Config</span>
      </NavLink>

      <NavLink
        to="/dashboard"
        className={({ isActive }) =>
          `nav-link ${isActive ? "active" : ""}`
        }
      >
        <span className="nav-icon">📊</span>
        <span>Dashboard</span>
      </NavLink>
    </nav>

      <Routes>
        <Route path="/" element={<ConfigPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;