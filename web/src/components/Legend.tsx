import { BUCKET_COLORS, BUCKET_LABELS } from "../lib/colors";

export default function Legend() {
  return (
    <div className="legend">
      {BUCKET_COLORS.map((c, i) => (
        <span key={c}>
          <i style={{ background: c }} /> {BUCKET_LABELS[i]}
        </span>
      ))}
    </div>
  );
}
