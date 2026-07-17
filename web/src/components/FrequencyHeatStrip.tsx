import { Fragment, type CSSProperties } from "react";
import type { Destination } from "../lib/types";

const DAYPARTS = [
  { name: "morning", label: "Morning", start: 0, end: 12 },
  { name: "afternoon", label: "Afternoon", start: 12, end: 18 },
  { name: "evening", label: "Evening", start: 18, end: 24 },
] as const;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

export interface HistogramRow {
  date: string;
  weekday: string;
  dayparts: number[];
}

export function histogramRows(histogram: Destination["histogram"]): HistogramRow[] | null {
  if (!histogram) return null;
  const entries = Object.entries(histogram).sort(([left], [right]) => left.localeCompare(right));
  if (!entries.length || entries.some(([, bins]) => !Array.isArray(bins) || bins.length !== 24
    || bins.some((count) => !Number.isFinite(count) || count < 0))) return null;
  return entries.map(([date, bins]) => ({
    date,
    weekday: WEEKDAYS[new Date(`${date}T00:00:00Z`).getUTCDay()],
    dayparts: DAYPARTS.map(({ start, end }) => bins.slice(start, end)
      .reduce((total, count) => total + count, 0)),
  }));
}

/** Faint daypart glyphs: sunrise, sun, crescent moon. Stroke follows text color. */
function DaypartIcon({ part }: { part: (typeof DAYPARTS)[number]["name"] }) {
  const shared = {
    className: "frequency-daypart-icon",
    viewBox: "0 0 16 16",
    "aria-hidden": true,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round",
  } as const;
  if (part === "morning") {
    return (
      <svg {...shared}>
        <path d="M4.5 11a3.5 3.5 0 0 1 7 0" />
        <line x1="1.5" y1="11" x2="14.5" y2="11" />
        <line x1="8" y1="2.5" x2="8" y2="4.5" />
        <line x1="3.4" y1="5.4" x2="4.8" y2="6.8" />
        <line x1="12.6" y1="5.4" x2="11.2" y2="6.8" />
      </svg>
    );
  }
  if (part === "afternoon") {
    return (
      <svg {...shared}>
        <circle cx="8" cy="8" r="3" />
        <line x1="8" y1="1.5" x2="8" y2="3" />
        <line x1="8" y1="13" x2="8" y2="14.5" />
        <line x1="1.5" y1="8" x2="3" y2="8" />
        <line x1="13" y1="8" x2="14.5" y2="8" />
        <line x1="3.4" y1="3.4" x2="4.5" y2="4.5" />
        <line x1="11.5" y1="11.5" x2="12.6" y2="12.6" />
        <line x1="3.4" y1="12.6" x2="4.5" y2="11.5" />
        <line x1="11.5" y1="4.5" x2="12.6" y2="3.4" />
      </svg>
    );
  }
  return (
    <svg {...shared}>
      <path d="M12.9 9.7A5.4 5.4 0 1 1 6.3 3.1a4.3 4.3 0 0 0 6.6 6.6Z" />
    </svg>
  );
}

interface Props {
  rows: HistogramRow[];
  expanded: boolean;
  legsId: string;
  onToggle: () => void;
}

export default function FrequencyHeatStrip({ rows, expanded, legsId, onToggle }: Props) {
  const maximum = Math.max(...rows.flatMap((row) => row.dayparts));
  return (
    <>
      <button type="button" className="frequency-heat-strip"
              aria-label="Toggle connection details" aria-expanded={expanded}
              aria-controls={legsId} onClick={onToggle}>
        <span className="frequency-heat-grid"
              style={{ "--heat-days": rows.length } as CSSProperties}>
          <span className="frequency-heat-corner" aria-hidden="true" />
          {rows.map((row) => (
            <span className="frequency-heat-day" key={row.date}>{row.weekday}</span>
          ))}
          {DAYPARTS.map((daypart, index) => (
            <Fragment key={daypart.name}>
              <span className="frequency-heat-daypart" title={daypart.label}
                    aria-label={daypart.label}>
                <DaypartIcon part={daypart.name} />
                <span className="frequency-daypart-word" aria-hidden="true">{daypart.label}</span>
              </span>
              {rows.map((row) => {
                const count = row.dayparts[index];
                const level = count === 0 ? 0 : Math.max(1, Math.ceil(count / maximum * 4));
                const detail = `${row.weekday} ${daypart.name}: ${count} direct trains`;
                return <span className={`frequency-heat-cell frequency-heat-level-${level}`}
                             title={detail} aria-label={detail} key={row.date} />;
              })}
            </Fragment>
          ))}
        </span>
        <span className="frequency-heat-legend">
          <span className="frequency-heat-legend-count">0</span>
          {[0, 1, 2, 3, 4].map((level) => (
            <span className={`frequency-heat-swatch frequency-heat-level-${level}`}
                  aria-hidden="true" key={level} />
          ))}
          <span className="frequency-heat-legend-count">{maximum}</span>
          <span className="frequency-heat-legend-caption">direct trains / daypart</span>
        </span>
      </button>
      <p className="frequency-heat-note">Sampled timetable evidence, not a promise.</p>
    </>
  );
}
