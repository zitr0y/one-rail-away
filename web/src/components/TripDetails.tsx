import { useEffect, useRef, useState } from "react";
import { bookingUrl, friendlyDateLabel, localDate, shiftDate } from "../lib/booking";
import { bestJourney, type MaxTrains } from "../lib/geojson";
import type { Destination, Station } from "../lib/types";

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
        ? `nonstop · ${dest.direct_per_day}× per day`
        : `${journey.trains} trains`}</p>
      <ol className="legs">
        {journey.legs.map((leg) => (
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
