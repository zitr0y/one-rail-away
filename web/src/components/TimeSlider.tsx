export default function TimeSlider(props: { value: number; onChange: (v: number) => void }) {
  const label = props.value >= 1440 ? "any duration" : `≤ ${Math.round(props.value / 60)} h`;
  return (
    <label className="time-slider">
      Max travel time: <strong>{label}</strong>
      <input type="range" min={60} max={1440} step={60} value={props.value}
             onChange={(e) => props.onChange(Number(e.target.value))} />
    </label>
  );
}
