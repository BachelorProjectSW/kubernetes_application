import {
  BrowserRouter,
  Routes,
  Route,
  NavLink,
  useNavigate,
} from "react-router-dom";
import { useEffect, useState } from "react";
import AllConfigs from "./components/play_around";
import { handleSubmit } from "./components/submitData";
import DashboardPage from "./pages/DashboardPage";
import "./index.css";

function ConfigPage() {
  const navigate = useNavigate();

  const [testStatus, setTestStatus] = useState("idle");
  const [hasSeenRunning, setHasSeenRunning] = useState(false);
  const [trackedConfigId, setTrackedConfigId] = useState(null);
  const [statusError, setStatusError] = useState("");

  const isLocked = testStatus === "running" || testStatus === "stopping";

  const fetchTestStatus = async () => {
    try {
      const res = await fetch("http://100.109.95.2:8099/test_status");

      if (!res.ok) {
        throw new Error("Failed to fetch test status");
      }

      const json = await res.json();

      setTestStatus(json.status);

      if (
        (json.status === "running" || json.status === "stopping") &&
        json.current_config_id
      ) {
        setHasSeenRunning(true);
        setTrackedConfigId(json.current_config_id);
      }

      setStatusError("");
    } catch (err) {
      console.error("Error fetching test status:", err);
      setStatusError("Could not read test status");
    }
  };

  // Check status once when the page opens
  useEffect(() => {
    fetchTestStatus();
  }, []);

  // While a test is running, keep checking until it becomes idle
  useEffect(() => {
    if (!isLocked) return;

    const interval = setInterval(() => {
      fetchTestStatus();
    }, 1500);

    return () => clearInterval(interval);
  }, [isLocked]);

  // Redirect only if this page has actually seen a running test become idle
  useEffect(() => {
    if (testStatus === "idle" && hasSeenRunning && trackedConfigId) {
      navigate(`/dashboard?config_id=${encodeURIComponent(trackedConfigId)}`);
    }
  }, [testStatus, hasSeenRunning, trackedConfigId, navigate]);

  const handleConfigSubmit = async (...args) => {
    try {
      await handleSubmit(...args);

      // After pressing Start Test, ask backend for real status
      await fetchTestStatus();
    } catch (err) {
      console.error("Error starting test:", err);
      setStatusError("Failed to start test");
    }
  };

  return (
    <div className="config-page-shell">
      <div className={`config-page-content ${isLocked ? "locked" : ""}`}>
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

        <AllConfigs onSubmit={handleConfigSubmit} />
      </div>

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
  );
}
function App() {
  return (
    <BrowserRouter>
      <nav className="top-nav">
        <NavLink
          to="/"
          end
          className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
        >
          <span className="nav-icon">📝</span>
          <span>Config</span>
        </NavLink>

        <NavLink
          to="/dashboard"
          className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
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
