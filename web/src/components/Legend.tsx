import { BUCKET_COLORS, BUCKET_LABELS } from "../lib/colors";
import { VEIL_LEGEND } from "../lib/coverage";

export default function Legend() {
  return (
    <div className="legend">
      {BUCKET_COLORS.map((c, i) => (
        <span key={c}>
          <i style={{ background: c }} /> {BUCKET_LABELS[i]}
        </span>
      ))}
      <span>
        <i style={{ background: "#6b7280", opacity: 0.25 }} /> {VEIL_LEGEND}
      </span>
    </div>
  );
}
