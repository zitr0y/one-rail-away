import { BUCKET_COLORS } from "../lib/colors";

// The slider doubles as the color legend: its track carries the bucket gradient,
// so travel-time → color is read directly off the control. It caps at 16 h; the
// top position means "max" (no upper limit) so the long-tail >10 h purple can't
// dominate the scale.
const MIN = 60; // 1 h
export const TIME_MAX = 960; // 16 h; value >= TIME_MAX means "max" (unlimited)
const SPAN = TIME_MAX - MIN;

// Bucket boundaries in minutes, matching timeBucket() in geojson.ts (180/360/600).
const BOUNDS = [180, 360, 600];
const pct = (m: number) => Math.round(((m - MIN) / SPAN) * 1000) / 10;
const GRADIENT =
  `linear-gradient(90deg,` +
  ` ${BUCKET_COLORS[0]} 0 ${pct(BOUNDS[0])}%,` +
  ` ${BUCKET_COLORS[1]} ${pct(BOUNDS[0])}% ${pct(BOUNDS[1])}%,` +
  ` ${BUCKET_COLORS[2]} ${pct(BOUNDS[1])}% ${pct(BOUNDS[2])}%,` +
  ` ${BUCKET_COLORS[3]} ${pct(BOUNDS[2])}% 100%)`;

export default function TimeSlider(props: { value: number; onChange: (v: number) => void }) {
  const atMax = props.value >= TIME_MAX;
  const label = atMax ? "max" : `≤ ${Math.round(props.value / 60)} h`;
  return (
    <label className="time-slider">
      Max travel time: <strong>{label}</strong>
      <input type="range" min={MIN} max={TIME_MAX} step={60}
             value={Math.min(props.value, TIME_MAX)}
             onChange={(e) => props.onChange(Number(e.target.value))}
             style={{ background: GRADIENT }} />
      <span className="time-scale"><span>1 h</span><span>max</span></span>
    </label>
  );
}
