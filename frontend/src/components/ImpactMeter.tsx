import { formatDollars, formatPercent } from "../data";

interface Props {
  savings: number;
  totalExposure: number;
}

export default function ImpactMeter({ savings, totalExposure }: Props) {
  const pct = totalExposure > 0 ? Math.min(1, savings / totalExposure) : 0;

  return (
    <div className="impact-meter">
      <div className="impact-meter-header">
        <span className="impact-meter-value">{formatDollars(savings)}</span>
        <span className="impact-meter-pct">{formatPercent(pct)} of exposure</span>
      </div>
      <div className="impact-meter-track">
        <div
          className="impact-meter-fill"
          style={{ width: `${(pct * 100).toFixed(1)}%` }}
        />
      </div>
    </div>
  );
}
