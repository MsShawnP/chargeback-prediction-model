export interface RiskEntry {
  sku: string;
  retailer: string;
  ship_date: string | null;
  probability: number;
  dollar_exposure: number;
  attribution_string: string;
  risk_tier: "HIGH" | "MEDIUM" | "LOW";
}

export interface SimulatorEntry {
  sku: string;
  retailer: string;
  ship_date: string | null;
  probability: number;
  dollar_exposure: number;
  attribution_string: string;
  risk_tier: "HIGH" | "MEDIUM" | "LOW";
  shap_values: Record<string, number>;
}

export interface Summary {
  total_chargeback_amount: number;
  total_preventable: number;
  preventable_pct: number;
  root_cause_counts: Record<string, number>;
  model_auc: number;
}
