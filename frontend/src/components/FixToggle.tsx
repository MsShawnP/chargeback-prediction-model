interface Props {
  featureKey: string;
  label: string;
  affectedCount: number;
  active: boolean;
  onToggle: (key: string) => void;
}

export default function FixToggle({ featureKey, label, affectedCount, active, onToggle }: Props) {
  return (
    <div
      className={`fix-toggle${active ? " fix-toggle-active" : ""}`}
      onClick={() => onToggle(featureKey)}
      role="switch"
      aria-checked={active}
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onToggle(featureKey); }}
    >
      <div className="fix-toggle-track">
        <div className="fix-toggle-thumb" />
      </div>
      <div className="fix-toggle-info">
        <span className="fix-toggle-label">{label}</span>
        <span className="fix-toggle-count">
          {affectedCount} high-risk shipment{affectedCount !== 1 ? "s" : ""} affected
        </span>
      </div>
    </div>
  );
}
