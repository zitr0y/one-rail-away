import type { MaxTrains } from "../lib/geojson";

const OPTIONS: { value: MaxTrains; label: string }[] = [
  { value: 1, label: "Nonstop" },
  { value: 2, label: "One stop" },
  { value: 3, label: "Two stops" },
];

export default function StopToggle(props: { value: MaxTrains; onChange: (v: MaxTrains) => void }) {
  return (
    <div className="stop-toggle" role="group" aria-label="Maximum trains">
      {OPTIONS.map((o) => (
        <button key={o.value} className={o.value === props.value ? "active" : ""}
                onClick={() => props.onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
