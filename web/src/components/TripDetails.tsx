import { useEffect, useRef, useState } from "react";
import { bookingUrl, friendlyDateLabel, localDate, shiftDate } from "../lib/booking";
import { bestJourney, type MaxTrains } from "../lib/geojson";
import type { Destination, Station, TransferMode } from "../lib/types";
import FrequencyHeatStrip, { histogramRows } from "./FrequencyHeatStrip";

const TRANSFER_MODE_ICONS: Record<TransferMode, string> = {
  walk: "🚶",
  metro: "🚇",
  tram: "🚋",
  cercanias: "🚆",
  rer: "🚆",
  "train-shuttle": "🚆",
  bus: "🚌",
};

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
  const dateInputRef = useRef<HTMLInputElement>(null);
  const today = localDate();
  const rows = histogramRows(dest.histogram);

  useEffect(() => {
    setBookingDate(localDate(1));
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
      <ol className="legs">
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
      {rows && <FrequencyHeatStrip rows={rows} />}
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
