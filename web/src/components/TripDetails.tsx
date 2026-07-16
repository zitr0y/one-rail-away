import { useEffect, useId, useRef, useState } from "react";
import { bookingUrl, friendlyDateLabel, localDate, shiftDate } from "../lib/booking";
import { bestJourney, type MaxTrains } from "../lib/geojson";
import type { Destination, Station, TransferMode } from "../lib/types";

const TRANSFER_MODE_ICONS: Record<TransferMode, string> = {
  walk: "🚶",
  metro: "🚇",
  tram: "🚋",
  cercanias: "🚆",
  rer: "🚆",
  "train-shuttle": "🚆",
  bus: "🚌",
};

const DAYPARTS = [
  { name: "morning", start: 0, end: 12 },
  { name: "afternoon", start: 12, end: 18 },
  { name: "evening", start: 18, end: 24 },
] as const;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

interface HistogramRow {
  date: string;
  weekday: string;
  dayparts: number[];
}

function histogramRows(histogram: Destination["histogram"]): HistogramRow[] | null {
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

export function transferModeIcon(mode: TransferMode): string {
  return TRANSFER_MODE_ICONS[mode];
}

export function frequencyLabel(dest: Destination): string {
  const f = dest.frequency;
  if (!f) return `${dest.direct_per_day}× per day`;
  const availability = f.availability === "coverage_limited"
    ? `limited feed coverage · route found on ${f.available_days}/${f.sample_days} covered dates`
    : f.availability === "year_round"
    ? "available on every sampled date"
    : f.available_days > 0
    ? `limited service · found on ${f.available_days}/${f.sample_days} selected dates`
    : "not running in the selected service week";
  if (!f.direct_trips) return availability;
  if (f.direct_days === f.sample_days && f.direct_per_active_day != null) {
    return `${f.direct_per_active_day} direct trains per day · ${availability}`;
  }
  return `about ${f.weekly_direct_estimate ?? 0} direct trains per week · ${availability}`;
}

interface Props {
  origin: Station;
  destination: Station;
  dest: Destination;
  maxTrains: MaxTrains;
  stationsById: Map<string, Station>;
}

export default function TripDetails(
  { origin, destination, dest, maxTrains, stationsById }: Props,
) {
  const [bookingDate, setBookingDate] = useState(() => localDate(1));
  const [detailsExpanded, setDetailsExpanded] = useState(false);
  const dateInputRef = useRef<HTMLInputElement>(null);
  const legsId = useId();
  const today = localDate();
  const rows = histogramRows(dest.histogram);
  const maximum = rows ? Math.max(...rows.flatMap((row) => row.dayparts)) : 0;

  useEffect(() => {
    setBookingDate(localDate(1));
    setDetailsExpanded(false);
  }, [origin.id, destination.id]);

  const openCalendar = () => {
    const input = dateInputRef.current;
    if (!input) return;
    try {
      input.showPicker();
    } catch {
      input.click();
    }
  };

  const journey = bestJourney(dest, maxTrains);
  if (!journey) return <p className="hint">No route within your filters.</p>;
  const h = Math.floor(journey.duration_min / 60);
  const m = journey.duration_min % 60;
  return (
    <div className="trip-details">
      <h2>{origin.name} → {destination.name}</h2>
      <p className="duration">{h} h {m ? `${m} min` : ""} · {journey.trains === 1
        ? "nonstop"
        : `${journey.trains} trains`}{!rows && ` · ${frequencyLabel(dest)}`}</p>
      {rows && <>
        <button type="button" className="frequency-heat-strip"
                aria-label="Toggle connection details" aria-expanded={detailsExpanded}
                aria-controls={legsId} onClick={() => setDetailsExpanded((expanded) => !expanded)}>
          {rows.map((row) => (
            <span className="frequency-heat-row" key={row.date}>
              <span className="frequency-heat-weekday">{row.weekday}</span>
              {row.dayparts.map((count, index) => {
                const level = count === 0 ? 0 : Math.max(1, Math.ceil(count / maximum * 4));
                return <span className={`frequency-heat-cell frequency-heat-level-${level}`}
                             aria-label={`${row.weekday} ${DAYPARTS[index].name}: ${count} connections`}
                             key={DAYPARTS[index].name} />;
              })}
            </span>
          ))}
        </button>
        <p className="frequency-heat-note">Sampled timetable evidence, not a promise.</p>
      </>}
      <ol id={legsId} className="legs" hidden={rows ? !detailsExpanded : undefined}>
        {journey.legs.map((leg) => leg.type === "transfer" ? (
          <li className="transfer-leg" key={`transfer-${leg.from_id}-${leg.to_id}`}>
            <span className="transfer-icon" aria-hidden="true">{transferModeIcon(leg.mode)}</span>
            {" "}~{leg.minutes} min {leg.mode} to{" "}
            {stationsById.get(leg.to_id)?.name ?? leg.to_id}
          </li>
        ) : (
          <li key={`${leg.train}-${leg.to}`}>
            <strong>{leg.train}</strong> {stationsById.get(leg.from)?.name ?? leg.from}
            {" → "} {stationsById.get(leg.to)?.name ?? leg.to}
          </li>
        ))}
      </ol>
      <div className="booking-date-picker">
        <input ref={dateInputRef} className="booking-date-native" type="date"
               value={bookingDate} min={today} tabIndex={-1}
               aria-label="Travel date" onChange={(event) => setBookingDate(event.target.value)} />
        <button type="button" className="booking-date-step" aria-label="Previous day"
                disabled={bookingDate === today}
                onClick={() => setBookingDate(shiftDate(bookingDate, -1))}>‹</button>
        <button type="button" className="booking-date-current" onClick={openCalendar}
                aria-label={`Choose travel date, ${friendlyDateLabel(bookingDate, today)}`}>
          {friendlyDateLabel(bookingDate, today)}
        </button>
        <button type="button" className="booking-date-step" aria-label="Next day"
                onClick={() => setBookingDate(shiftDate(bookingDate, 1))}>›</button>
      </div>
      <a className="book" href={bookingUrl()}
         target="_blank" rel="noopener noreferrer">
        Search on Trainline
      </a>
    </div>
  );
}
