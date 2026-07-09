import { useEffect, useMemo, useState } from "react";
import MapView from "./components/Map";
import JourneyCard from "./components/JourneyCard";
import Legend from "./components/Legend";
import SearchBox from "./components/SearchBox";
import StopToggle from "./components/StopToggle";
import TimeSlider from "./components/TimeSlider";
import { api } from "./lib/api";
import type { MaxTrains } from "./lib/geojson";
import { statusText } from "./lib/status";
import type { ReachFile, Station } from "./lib/types";

export default function App() {
  const [stations, setStations] = useState<Station[]>([]);
  const [reach, setReach] = useState<ReachFile | null>(null);
  const [maxTrains, setMaxTrains] = useState<MaxTrains>(1);
  const [maxMinutes, setMaxMinutes] = useState(1440);
  const [selectedDest, setSelectedDest] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const stationsById = useMemo(() => new Map(stations.map((s) => [s.id, s])), [stations]);

  useEffect(() => {
    api.getStations().then((r) => setStations(r.stations)).catch((e) => setError(String(e)));
  }, []);

  function selectOrigin(id: string) {
    setSelectedDest(null);
    api.getReach(id).then(setReach).catch((e) => setError(String(e)));
  }

  const origin = reach ? stationsById.get(reach.origin) : undefined;
  const dest = selectedDest && reach
    ? reach.destinations.find((d) => d.id === selectedDest) : undefined;

  return (
    <div className="app">
      <MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={maxMinutes}
               onSelectOrigin={selectOrigin} onSelectDestination={setSelectedDest} />
      <header className="panel">
        <h1>onestopeurope</h1>
        <p className="tagline">nonstopeurope with onestopeurope</p>
        <SearchBox onSelect={(s) => selectOrigin(s.id)} />
        <StopToggle value={maxTrains} onChange={setMaxTrains} />
        <TimeSlider value={maxMinutes} onChange={setMaxMinutes} />
        <Legend />
        {!reach && <p className="hint">Search or click a station to begin.</p>}
        {error && <p className="error">{error}</p>}
      </header>
      {origin && dest && stationsById.get(dest.id) && (
        <JourneyCard origin={origin} destination={stationsById.get(dest.id)!} dest={dest}
                     maxTrains={maxTrains} stationsById={stationsById}
                     onClose={() => setSelectedDest(null)} />
      )}
      {origin && (
        <div className="status-bar">
          {statusText(origin.name, (dest && stationsById.get(dest.id)?.name) || null)}
        </div>
      )}
    </div>
  );
}
