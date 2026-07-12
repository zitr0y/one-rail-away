import { useCallback, useEffect, useMemo, useState } from "react";
import { emptyClickAction, swapDest } from "./lib/selection";
import { armedTarget, routeMapClick, type ActiveField } from "./lib/mapclick";
import MapView from "./components/Map";
import JourneyPlanner from "./components/JourneyPlanner";
import { api } from "./lib/api";
import type { MaxTrains } from "./lib/geojson";
import type { FeaturePick } from "./lib/pickfeature";
import type { ReachFile, Station } from "./lib/types";
import { useTheme } from "./lib/theme";

export default function App() {
  const [stations, setStations] = useState<Station[]>([]);
  const [reach, setReach] = useState<ReachFile | null>(null);
  const [maxTrains, setMaxTrains] = useState<MaxTrains>(1);
  const [maxMinutes, setMaxMinutes] = useState(1440);
  const [selectedDest, setSelectedDest] = useState<string | null>(null);
  const [activeField, setActiveField] = useState<ActiveField>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, toggleTheme] = useTheme();

  const stationsById = useMemo(() => new Map(stations.map((s) => [s.id, s])), [stations]);

  useEffect(() => {
    api.getStations().then((r) => setStations(r.stations)).catch((e) => setError(String(e)));
  }, []);

  const selectOrigin = useCallback((id: string) => {
    setSelectedDest(null);
    setHint(null);
    setActiveField("to"); // auto-advance arming to To
    api.getReach(id).then(setReach).catch((e) => setError(String(e)));
  }, []);

  const clearSelection = useCallback(() => {
    setReach(null);
    setSelectedDest(null);
    setHint(null);
    setActiveField(null);
  }, []);

  const selectDest = useCallback((id: string) => {
    setHint(null);
    setSelectedDest(id);
  }, []);

  const swapSelection = useCallback(() => {
    if (!selectedDest || !reach) return;
    const destId = selectedDest;
    const prevOrigin = reach.origin;
    setSelectedDest(null);
    api.getReach(destId).then((newReach) => {
      setReach(newReach);
      setSelectedDest(swapDest(newReach.destinations, prevOrigin));
    }).catch((e) => setError(String(e)));
  }, [selectedDest, reach]);

  const origin = reach ? stationsById.get(reach.origin) : undefined;
  const dest = selectedDest && reach
    ? reach.destinations.find((d) => d.id === selectedDest) : undefined;
  const destination = dest ? stationsById.get(dest.id) : undefined;

  const onStationClick = useCallback((pick: FeaturePick) => {
    const target = armedTarget(activeField, reach !== null);
    const routed = routeMapClick(pick, target);
    if (routed.action === "origin") selectOrigin(routed.id);
    else if (routed.action === "dest") selectDest(routed.id);
    else setHint(`Not reachable from ${origin?.name ?? "the origin"} within your filters.`);
  }, [activeField, reach, origin, selectOrigin, selectDest]);

  const onEmptyClick = useCallback(() => {
    const action = emptyClickAction(selectedDest !== null, reach !== null);
    if (action === "clearDest") setSelectedDest(null);
    else if (action === "clearAll") clearSelection();
  }, [selectedDest, reach, clearSelection]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
      if (selectedDest) setSelectedDest(null);
      else if (reach) clearSelection();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [reach, selectedDest, clearSelection]);

  return (
    <div className="app">
      <MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={maxMinutes}
               selectedDest={selectedDest} theme={theme}
               onStationClick={onStationClick} onEmptyClick={onEmptyClick} />
      <header className="header-bar">
        <span className="header-brand">
          <img src="/logo-train-light.svg" alt="" className="header-train" />
          <span className="header-wordmark">onestop<span className="header-wordmark-eu">europe</span></span>
          <span className="header-endstop" aria-hidden="true" />
        </span>
        <span className="header-tagline">nonstopeurope with onestopeurope</span>
        <button className="theme-toggle" onClick={toggleTheme}
                aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}>
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </header>
      <JourneyPlanner
        reach={reach} stationsById={stationsById}
        origin={origin} destination={destination} dest={dest}
        maxTrains={maxTrains} maxMinutes={maxMinutes}
        error={error} hint={hint}
        onSetOrigin={(s) => selectOrigin(s.id)}
        onClearOrigin={clearSelection}
        onSetDest={(s) => selectDest(s.id)}
        onClearDest={() => { setSelectedDest(null); setHint(null); }}
        onSwap={swapSelection}
        onArm={setActiveField}
        onMaxTrains={setMaxTrains}
        onMaxMinutes={setMaxMinutes}
      />
    </div>
  );
}
