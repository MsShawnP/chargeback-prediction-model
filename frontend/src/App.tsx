import { useEffect, useState } from "react";
import type { RiskEntry, SimulatorEntry, Summary } from "./types";
import { loadRiskLedger, loadSimulator, loadSummary } from "./data";
import RiskLedger from "./views/RiskLedger";
import Simulator from "./views/Simulator";
import "./App.css";

type Tab = "ledger" | "simulator";

export default function App() {
  const [riskLedger, setRiskLedger] = useState<RiskEntry[] | null>(null);
  const [simulator, setSimulator] = useState<SimulatorEntry[] | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("ledger");

  useEffect(() => {
    Promise.all([loadRiskLedger(), loadSimulator(), loadSummary()])
      .then(([rl, sim, sum]) => {
        setRiskLedger(rl);
        setSimulator(sim);
        setSummary(sum);
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  if (error) return <div className="error">Error loading data: {error}</div>;
  if (riskLedger === null || simulator === null || summary === null) {
    return <div className="loading">Loading…</div>;
  }

  return (
    <div className="app">
      <header>
        <h1>Cinderhaven Provisions — Chargeback Risk</h1>
        <p className="subtitle">
          Predictive model · Forward risk scoring · Prevention roadmap
        </p>
      </header>

      <nav className="tab-nav">
        <button
          className={`tab-btn${activeTab === "ledger" ? " active" : ""}`}
          onClick={() => setActiveTab("ledger")}
        >
          Risk Ledger
        </button>
        <button
          className={`tab-btn${activeTab === "simulator" ? " active" : ""}`}
          onClick={() => setActiveTab("simulator")}
        >
          Intervention Simulator
        </button>
      </nav>

      {activeTab === "ledger" && <RiskLedger entries={riskLedger} />}
      {activeTab === "simulator" && (
        <Simulator entries={simulator} summary={summary} />
      )}
    </div>
  );
}
