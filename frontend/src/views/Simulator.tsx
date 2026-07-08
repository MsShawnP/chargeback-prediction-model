import { useMemo, useState } from "react";
import type { SimulatorEntry, Summary } from "../types";
import { formatDollars, formatPercent } from "../data";
import FixToggle from "../components/FixToggle";
import ImpactMeter from "../components/ImpactMeter";
import "./Simulator.css";

interface Props {
  entries: SimulatorEntry[];
  summary: Summary;
}

const FIXABLE_FEATURES: Array<{ key: string; label: string }> = [
  { key: "gtin14_missing", label: "Fix GTIN-14 labeling" },
  { key: "upc_missing", label: "Fix UPC labeling" },
  { key: "case_dims_missing", label: "Fix case dimensions" },
  { key: "case_weight_missing", label: "Fix case weight" },
  { key: "asn_sent_late", label: "Send ASNs on time" },
];

interface SavingsResult {
  savings: number;
  prevented: number;
}

// ILLUSTRATIVE APPROXIMATION — not an exact probability recomputation.
// shap_values here are TreeExplainer margins in LOG-ODDS space, while
// row.probability is in probability space. Subtracting a log-odds margin
// directly from a probability is dimensionally inexact, so the projected
// impact below is a directional estimate, not a calibrated prediction. A
// rigorous version would map logit(prob) - margin back through the sigmoid.
// The panel is labelled "illustrative" to reflect this.
function computeSavings(entries: SimulatorEntry[], active: Set<string>): SavingsResult {
  if (active.size === 0) return { savings: 0, prevented: 0 };

  let savings = 0;
  let prevented = 0;

  for (const row of entries) {
    let activeReduction = 0;
    for (const feature of active) {
      const shap = row.shap_values[feature] ?? 0;
      if (shap > 0) activeReduction += shap;
    }
    if (activeReduction === 0) continue;

    const newProb = Math.max(0, row.probability - activeReduction);
    const delta = row.probability - newProb;
    const orderValue = row.probability > 0 ? row.dollar_exposure / row.probability : 0;
    savings += delta * orderValue;
    prevented += delta;
  }

  return { savings, prevented };
}

function countAffected(entries: SimulatorEntry[], feature: string): number {
  return entries.filter(
    (e) => e.risk_tier === "HIGH" && (e.shap_values[feature] ?? 0) > 0
  ).length;
}

export default function Simulator({ entries, summary }: Props) {
  const [activeToggles, setActiveToggles] = useState<Set<string>>(new Set());

  const { savings, prevented } = useMemo(
    () => computeSavings(entries, activeToggles),
    [entries, activeToggles]
  );

  const totalExposure = useMemo(
    () => entries.reduce((sum, e) => sum + e.dollar_exposure, 0),
    [entries]
  );

  const preventionPct = totalExposure > 0 ? savings / totalExposure : 0;

  function toggleFeature(key: string) {
    setActiveToggles((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const hasToggles = activeToggles.size > 0;
  const toggleCount = activeToggles.size;

  return (
    <div className="simulator">
      <div className="simulator-layout">
        <div className="simulator-controls">
          <h2>Intervention Controls</h2>
          <p className="section-description">
            Toggle upstream fixes to project their impact on chargeback exposure.
            Projections are an <strong>illustrative</strong> approximation from pre-scored
            SHAP attribution values (log-odds margins applied directly in probability
            space) — directional, not a calibrated forecast, and no backend call required.
          </p>
          {FIXABLE_FEATURES.map(({ key, label }) => (
            <FixToggle
              key={key}
              featureKey={key}
              label={label}
              affectedCount={countAffected(entries, key)}
              active={activeToggles.has(key)}
              onToggle={toggleFeature}
            />
          ))}
        </div>

        <div className="simulator-results">
          <h2>Projected Impact (illustrative)</h2>
          {hasToggles ? (
            <>
              <ImpactMeter savings={savings} totalExposure={totalExposure} />
              <div className="result-stats">
                <div className="result-stat">
                  <span className="result-label">Chargebacks prevented</span>
                  <span className="result-value">{prevented.toFixed(1)}</span>
                </div>
                <div className="result-stat">
                  <span className="result-label">Dollar savings</span>
                  <span className="result-value result-value-savings">
                    {formatDollars(savings)}
                  </span>
                </div>
                <div className="result-stat">
                  <span className="result-label">% of total exposure</span>
                  <span className="result-value">{formatPercent(preventionPct)}</span>
                </div>
              </div>
              <div className="roi-callout">
                <p>
                  Fixing{" "}
                  {toggleCount === 1
                    ? "this condition"
                    : `these ${toggleCount} conditions`}{" "}
                  would prevent an estimated{" "}
                  <strong>{formatDollars(savings)}</strong> in projected
                  chargebacks — permanently.
                </p>
              </div>
              <p className="summary-note">
                Historical model: {formatDollars(summary.total_preventable)} (
                {formatPercent(summary.preventable_pct)}) of all chargebacks
                identified as preventable. Model AUC: {summary.model_auc.toFixed(3)}.
              </p>
            </>
          ) : (
            <div className="no-toggles">
              <p>Toggle a fix on the left to see its projected impact.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
