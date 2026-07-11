import { bookingUrl } from "../lib/booking";
import { bestJourney, type MaxTrains } from "../lib/geojson";
import type { Destination, Station } from "../lib/types";

const REF = import.meta.env.VITE_TRAINLINE_REF ?? "";

interface Props {
  origin: Station;
  destination: Station;
  dest: Destination;
  maxTrains: MaxTrains;
  stationsById: Map<string, Station>;
  onClose: () => void;
  onSwap: () => void;
}

export default function JourneyCard({ origin, destination, dest, maxTrains, stationsById, onClose, onSwap }: Props) {
  const journey = bestJourney(dest, maxTrains);
  if (!journey) return null;
  const h = Math.floor(journey.duration_min / 60);
  const m = journey.duration_min % 60;
  return (
    <div className="journey-card">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <h2>{origin.name} → {destination.name}</h2>
      <p className="duration">{h} h {m ? `${m} min` : ""} · {journey.trains === 1
        ? `nonstop · ${dest.direct_per_day}× per day`
        : `${journey.trains} trains`}</p>
      <div className="actions">
        <button className="action-btn" onClick={onSwap}>⇄ Swap</button>
      </div>
      <ol className="legs">
        {journey.legs.map((leg) => (
          <li key={`${leg.train}-${leg.to}`}>
            <strong>{leg.train}</strong> {stationsById.get(leg.from)?.name ?? leg.from}
            {" → "} {stationsById.get(leg.to)?.name ?? leg.to}
          </li>
        ))}
      </ol>
      <a className="book" href={bookingUrl(origin, destination, REF)} target="_blank" rel="noopener noreferrer">
        Book this trip
      </a>
      <p className="fineprint">Durations from a sample weekday — pick your date at checkout.</p>
    </div>
  );
}
