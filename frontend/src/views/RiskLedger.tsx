import { useMemo, useState } from "react";
import type { RiskEntry } from "../types";
import { formatDollars } from "../data";
import RiskBadge from "../components/RiskBadge";
import RetailerFilter from "../components/RetailerFilter";
import "./RiskLedger.css";

interface Props {
  entries: RiskEntry[];
}

type RiskTier = "HIGH" | "MEDIUM" | "LOW";

function rowKey(e: RiskEntry): string {
  return `${e.sku}__${e.retailer}__${e.ship_date ?? ""}`;
}

export default function RiskLedger({ entries }: Props) {
  const [pinnedKey, setPinnedKey] = useState<string | null>(null);
  const [retailerFilter, setRetailerFilter] = useState<string>("");
  const [tierFilter, setTierFilter] = useState<Set<RiskTier>>(new Set());

  const retailers = useMemo(
    () => [...new Set(entries.map((e) => e.retailer))].sort(),
    [entries]
  );

  const sorted = useMemo(
    () => [...entries].sort((a, b) => b.dollar_exposure - a.dollar_exposure),
    [entries]
  );

  const filtered = useMemo(() => {
    return sorted.filter((e) => {
      if (retailerFilter && e.retailer !== retailerFilter) return false;
      if (tierFilter.size > 0 && !tierFilter.has(e.risk_tier)) return false;
      return true;
    });
  }, [sorted, retailerFilter, tierFilter]);

  const totalExposure = useMemo(
    () => filtered.reduce((sum, e) => sum + e.dollar_exposure, 0),
    [filtered]
  );

  const highRiskCount = useMemo(
    () => filtered.filter((e) => e.risk_tier === "HIGH").length,
    [filtered]
  );

  const topSku = useMemo(() => {
    if (!filtered.length) return null;
    const bySkuExposure = new Map<string, number>();
    for (const e of filtered) {
      bySkuExposure.set(e.sku, (bySkuExposure.get(e.sku) ?? 0) + e.dollar_exposure);
    }
    return [...bySkuExposure.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
  }, [filtered]);

  const pinnedEntry = pinnedKey
    ? (entries.find((e) => rowKey(e) === pinnedKey) ?? null)
    : null;

  function togglePin(e: RiskEntry) {
    const key = rowKey(e);
    setPinnedKey((prev) => (prev === key ? null : key));
  }

  function toggleTier(tier: RiskTier) {
    setTierFilter((prev) => {
      const next = new Set(prev);
      if (next.has(tier)) next.delete(tier);
      else next.add(tier);
      return next;
    });
  }

  return (
    <div className="risk-ledger">
      <div className="summary-bar">
        <div className="summary-stat">
          <span className="summary-label">Total upcoming exposure</span>
          <span className="summary-value">{formatDollars(totalExposure)}</span>
        </div>
        <div className="summary-stat">
          <span className="summary-label">High-risk shipments</span>
          <span className="summary-value summary-value-high">{highRiskCount}</span>
        </div>
        <div className="summary-stat">
          <span className="summary-label">Top at-risk SKU</span>
          <span className="summary-value">{topSku ?? "—"}</span>
        </div>
      </div>

      <div className="filter-bar">
        <RetailerFilter
          retailers={retailers}
          value={retailerFilter}
          onChange={setRetailerFilter}
        />
        <div className="tier-chips">
          {(["HIGH", "MEDIUM", "LOW"] as RiskTier[]).map((tier) => (
            <button
              key={tier}
              className={`tier-chip tier-chip-${tier.toLowerCase()}${tierFilter.has(tier) ? " active" : ""}`}
              onClick={() => toggleTier(tier)}
            >
              {tier}
            </button>
          ))}
        </div>
      </div>

      {pinnedEntry && (
        <div className="pin-card">
          <div className="pin-card-header">
            <span className="pin-sku">{pinnedEntry.sku}</span>
            <RiskBadge tier={pinnedEntry.risk_tier} />
            <button className="pin-close" onClick={() => setPinnedKey(null)}>
              ✕
            </button>
          </div>
          <div className="pin-card-body">
            <div className="pin-detail">
              <span className="pin-detail-label">Retailer</span>
              <span className="pin-detail-value">{pinnedEntry.retailer}</span>
            </div>
            <div className="pin-detail">
              <span className="pin-detail-label">Ship date</span>
              <span className="pin-detail-value">{pinnedEntry.ship_date ?? "—"}</span>
            </div>
            <div className="pin-detail">
              <span className="pin-detail-label">Probability</span>
              <span className="pin-detail-value">
                {(pinnedEntry.probability * 100).toFixed(1)}%
              </span>
            </div>
            <div className="pin-detail">
              <span className="pin-detail-label">$ Exposure</span>
              <span className="pin-detail-value">
                {formatDollars(pinnedEntry.dollar_exposure)}
              </span>
            </div>
          </div>
          <div className="pin-attribution">
            <span className="pin-attribution-label">Why this shipment is at risk</span>
            <p className="pin-attribution-text">
              {pinnedEntry.attribution_string || "No attribution available."}
            </p>
          </div>
        </div>
      )}

      {filtered.length === 0 ? (
        <p className="empty">No shipments match the current filters.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Retailer</th>
              <th>Ship Date</th>
              <th>Risk</th>
              <th className="num">$ Exposure</th>
              <th>Attribution</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => {
              const key = rowKey(e);
              return (
                <tr
                  key={key}
                  className={`ledger-row${pinnedKey === key ? " pinned" : ""}`}
                  onClick={() => togglePin(e)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") togglePin(e); }}
                >
                  <td>{e.sku}</td>
                  <td>{e.retailer}</td>
                  <td>{e.ship_date ?? "—"}</td>
                  <td>
                    <RiskBadge tier={e.risk_tier} />
                  </td>
                  <td className="num">{formatDollars(e.dollar_exposure)}</td>
                  <td className="attribution-cell">
                    {e.attribution_string || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
