import { useState } from 'react';
import Ids from './experimentID';
import Start from './startTime';
import Weights from './weights';
import Power_schedular from './power_schedular';
import Workload from './workloadbalance';
import ClusterMangening from './cluster';
import GlobalScheduler from './global_schedular';
import StratoConfigs from './strato_config';
import Latency from './latency';
import Question from './question';

function AllConfigs({ onSubmit }) {
    const [inputs, setInputs] = useState({});

    const handleChange = (e) => {
        const { name, value } = e.target;

        setInputs(values => ({ ...values, [name]: value }));
    };

    return (
        <form onSubmit={(e) => onSubmit(e, inputs)}>

            {/* ── Identity row ── */}
            <div className="section-panel full-width" style={{ display: "flex", gap: "2rem", alignItems: "flex-end", flexWrap: "wrap" }}>
                <p className="panel-title">
                    <span className="panel-title-icon">🔖</span>
                    Experiment Identity
                </p>
                <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap", alignItems: "flex-end" }}>
                    <Ids inputs={inputs} setInputs={setInputs} handleChange={handleChange} />
                    <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                        <span style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}>Experiment Name</span>
                        <input
                            type="text"
                            name="name"
                            value={inputs.name || ""}
                            onChange={handleChange}
                            placeholder="e.g. baseline-run-01"
                            style={{ minWidth: "200px" }}
                        />
                    </label>
                </div>
            </div>

            {/* ── Timing ── */}
            <div className="section-panel full-width">
                <Start inputs={inputs} handleChange={handleChange} />
            </div>

            <div className="section-divider full-width">Scheduling &amp; Performance</div>

            {/* ── Weights + Power side by side ── */}
            <div className="section-panel">
                <Weights inputs={inputs} handleChange={handleChange} />
            </div>

            <div className="section-panel">
                <Power_schedular inputs={inputs} handleChange={handleChange} />
            </div>

            {/* ── Latency + Workload side by side ── */}
            <div className="section-panel">
                <Latency inputs={inputs} handleChange={handleChange} />
            </div>

            <div className="section-panel">
                <Workload inputs={inputs} handleChange={handleChange} />
            </div>

            {/* ── Question full width ── */}
            <div className="section-panel full-width">
                <Question inputs={inputs} handleChange={handleChange} />
            </div>

            <div className="section-divider full-width">Infrastructure</div>

            {/* ── Clusters full width ── */}
            <div className="section-panel full-width">
                <ClusterMangening inputs={inputs} setInputs={setInputs} />
            </div>

            {/* ── Global + Strato side by side ── */}
            <div className="section-panel">
                <GlobalScheduler inputs={inputs} handleChange={handleChange} />
            </div>

            <div className="section-panel">
                <StratoConfigs inputs={inputs} handleChange={handleChange} />
            </div>

            {/* ── Submit ── */}
            <div className="submit-row">
                <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                    All fields will be validated before submission
                </span>
                <button type="submit">⚡ Start Test</button>
            </div>

        </form>
    );
}

export default AllConfigs;
