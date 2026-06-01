interface Props {
  tier: "HIGH" | "MEDIUM" | "LOW";
}

export default function RiskBadge({ tier }: Props) {
  return (
    <span className={`risk-badge risk-badge-${tier.toLowerCase()}`}>
      {tier}
    </span>
  );
}
