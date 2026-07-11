import { useCallback, useEffect, useMemo, useState } from "react";
import { emptyClickAction, swapDest } from "./lib/selection";
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

  function clearSelection() {
    setReach(null);
    setSelectedDest(null);
  }

  function swapSelection() {
    if (!selectedDest || !reach) return;
    const destId = selectedDest;
    const prevOrigin = reach.origin;
    setSelectedDest(null);
    api.getReach(destId).then((newReach) => {
      setReach(newReach);
      setSelectedDest(swapDest(newReach.destinations, prevOrigin));
    }).catch((e) => setError(String(e)));
  }

  const onEmptyClick = useCallback(() => {
    const action = emptyClickAction(selectedDest !== null, reach !== null);
    if (action === "clearDest") setSelectedDest(null);
    else if (action === "clearAll") clearSelection();
  }, [selectedDest, reach]);

  const origin = reach ? stationsById.get(reach.origin) : undefined;
  const dest = selectedDest && reach
    ? reach.destinations.find((d) => d.id === selectedDest) : undefined;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      if (selectedDest) setSelectedDest(null);
      else if (reach) clearSelection();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [reach, selectedDest]);

  return (
    <div className="app">
      <MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={maxMinutes}
               selectedDest={selectedDest}
               onSelectOrigin={selectOrigin} onSelectDestination={setSelectedDest}
               onEmptyClick={onEmptyClick} />
      <header className="header-bar">
        <img src="/logo-mascot.svg" alt="" className="header-mascot" />
        <span className="header-wordmark">onestopeurope</span>
        <span className="header-tagline">nonstopeurope with onestopeurope</span>
      </header>
      <aside className="panel">
        <SearchBox onSelect={(s) => selectOrigin(s.id)} />
        <StopToggle value={maxTrains} onChange={setMaxTrains} />
        <TimeSlider value={maxMinutes} onChange={setMaxMinutes} />
        <Legend />
        {!reach && <p className="hint">Search or click a station to begin.</p>}
        {error && <p className="error">{error}</p>}
      </aside>
      {origin && dest && stationsById.get(dest.id) && (
        <JourneyCard origin={origin} destination={stationsById.get(dest.id)!} dest={dest}
                     maxTrains={maxTrains} stationsById={stationsById}
                     onClose={() => setSelectedDest(null)}
                     onSwap={swapSelection} />
      )}
      {origin && (
        <div className="status-bar">
          <span>{statusText(origin.name, (dest && stationsById.get(dest.id)?.name) || null)}</span>
          <button className="close" onClick={clearSelection} aria-label="Unselect station">×</button>
        </div>
      )}
    </div>
  );
}
