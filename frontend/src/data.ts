import type { RiskEntry, SimulatorEntry, Summary } from "./types";

const DEFAULT_SUMMARY: Summary = {
  total_chargeback_amount: 0,
  total_preventable: 0,
  preventable_pct: 0,
  root_cause_counts: {},
  model_auc: 0,
};

export async function loadRiskLedger(): Promise<RiskEntry[]> {
  const res = await fetch("/json/risk_ledger.json");
  if (res.status === 404) return [];
  if (!res.ok) throw new Error(`Failed to load risk_ledger.json: ${res.status}`);
  const data: unknown = await res.json();
  if (!Array.isArray(data)) throw new Error("risk_ledger.json: expected array");
  return data as RiskEntry[];
}

export async function loadSimulator(): Promise<SimulatorEntry[]> {
  const res = await fetch("/json/simulator.json");
  if (res.status === 404) return [];
  if (!res.ok) throw new Error(`Failed to load simulator.json: ${res.status}`);
  const data: unknown = await res.json();
  if (!Array.isArray(data)) throw new Error("simulator.json: expected array");
  return data as SimulatorEntry[];
}

export async function loadSummary(): Promise<Summary> {
  const res = await fetch("/json/summary.json");
  if (res.status === 404) return DEFAULT_SUMMARY;
  if (!res.ok) throw new Error(`Failed to load summary.json: ${res.status}`);
  const data: unknown = await res.json();
  return data as Summary;
}

export function formatDollars(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export function formatPercent(n: number, digits = 1): string {
  return `${(n * 100).toFixed(digits)}%`;
}
