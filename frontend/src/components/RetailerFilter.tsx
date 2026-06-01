interface Props {
  retailers: string[];
  value: string;
  onChange: (value: string) => void;
}

export default function RetailerFilter({ retailers, value, onChange }: Props) {
  return (
    <div className="retailer-filter">
      <label htmlFor="retailer-select">Retailer</label>
      <select
        id="retailer-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">All retailers</option>
        {retailers.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
    </div>
  );
}
