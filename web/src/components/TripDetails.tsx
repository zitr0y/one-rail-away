import { useEffect, useState } from "react";
import { bookingUrl, localDate } from "../lib/booking";
import { bestJourney, type MaxTrains } from "../lib/geojson";
import type { Destination, Station } from "../lib/types";

const REF = import.meta.env.VITE_TRAINLINE_REF ?? "";

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
  const today = localDate();

  useEffect(() => {
    setBookingDate(localDate(1));
  }, [origin.id, destination.id]);

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
      <label className="booking-date">
        <span>Travel date</span>
        <input type="date" value={bookingDate} min={today}
               onChange={(event) => setBookingDate(event.target.value)} />
      </label>
      <a className="book" href={bookingUrl(origin, destination, bookingDate, REF)}
         target="_blank" rel="noopener noreferrer">
        Book this trip
      </a>
      <p className="fineprint">Pick your time at checkout</p>
    </div>
  );
}
