import { useEffect, useId, useRef } from "react";
import { DATA_SOURCES_URL, IN_USE, WANTED_COUNTRIES, WANTED_OPERATORS } from "./aboutContent";

interface Props { onClose: () => void }

export default function AboutDialog({ onClose }: Props) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="about-backdrop" onClick={onClose}>
      <div className="about-panel" role="dialog" aria-modal="true" aria-labelledby={titleId}
           onClick={(e) => e.stopPropagation()}>
        <div className="about-head">
          <h2 id={titleId}>About onestopeurope</h2>
          <button ref={closeRef} type="button" className="about-close" aria-label="Close"
                  onClick={onClose}>×</button>
        </div>

        <h3>Why this map exists</h3>
        <p>Flying is often the default for trips in Europe, mostly because it’s hard to see
          what’s possible by train. onestopeurope shows, from any station, everywhere you can
          reach by train — and how many changes it takes. It starts with <strong>nonstop</strong>{" "}
          trains, because a journey without changes is the one people actually enjoy taking.</p>

        <h3>How to read it</h3>
        <p>Pick a station. Colours show travel time; lines show the routes. Switch between{" "}
          <strong>Nonstop</strong>, <strong>One stop</strong> and <strong>Two stops</strong> to
          allow changes. Tap a destination for example trains, how often they run, and a link
          to book.</p>

        <h3>Data</h3>
        <p><strong>Timetables from:</strong>{" "}
          {IN_USE.map((s) => `${s.operator} (${s.country})`).join(", ")}.</p>
        <p><strong>Not covered yet.</strong> No feed of their own: {WANTED_COUNTRIES.join(", ")}{" "}
          — trains <em>into</em> them show up, journeys <em>from</em> them don’t. Missing
          operators: {WANTED_OPERATORS.map((o) => `${o.operator} (${o.where})`).join(", ")}.</p>
        <p>Know an open timetable feed for one of these?{" "}
          <a href="/legal.html">Get in touch</a>. Full, current list:{" "}
          <a href={DATA_SOURCES_URL} target="_blank" rel="noopener noreferrer">data sources</a>.</p>

        <p className="about-foot">
          <a href="/legal.html">Legal notice</a> · <a href="/privacy.html">Privacy</a> ·
          Built by Aaron Bussche as a free side project.
        </p>
      </div>
    </div>
  );
}
