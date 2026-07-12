import { useCallback, useEffect, useMemo, useState } from "react";
import { emptyClickAction, swapDest } from "./lib/selection";
import { armedTarget, routeMapClick, type ActiveField } from "./lib/mapclick";
import MapView from "./components/Map";
import JourneyPlanner from "./components/JourneyPlanner";
import { TIME_MAX } from "./components/TimeSlider";
import { api } from "./lib/api";
import type { MaxTrains } from "./lib/geojson";
import type { FeaturePick } from "./lib/pickfeature";
import type { ReachFile, Station } from "./lib/types";
import { useTheme } from "./lib/theme";

export default function App() {
  const [stations, setStations] = useState<Station[]>([]);
  const [reach, setReach] = useState<ReachFile | null>(null);
  const [maxTrains, setMaxTrains] = useState<MaxTrains>(1);
  const [maxMinutes, setMaxMinutes] = useState(TIME_MAX); // start at "max" (no cap)
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
    // Picking a destination that needs more trains than the current filter bumps
    // the stop filter to accommodate it (rather than showing "no route").
    const d = reach?.destinations.find((x) => x.id === id);
    if (d) {
      const eff = maxMinutes >= TIME_MAX ? Infinity : maxMinutes;
      const within = d.journeys.filter((j) => j.duration_min <= eff);
      if (within.length) {
        const need = Math.min(...within.map((j) => j.trains)) as MaxTrains;
        setMaxTrains((cur) => (need > cur ? need : cur));
      }
    }
    setHint(null);
    setSelectedDest(id);
  }, [reach, maxMinutes]);

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

  // At the top of the slider ("max") there is no upper time limit.
  const filterMinutes = maxMinutes >= TIME_MAX ? Infinity : maxMinutes;
  const armed = armedTarget(activeField, reach !== null);

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
      <MapView stations={stations} reach={reach} maxTrains={maxTrains} maxMinutes={filterMinutes}
               selectedDest={selectedDest} theme={theme}
               onStationClick={onStationClick} onEmptyClick={onEmptyClick} />
      <header className="header-bar">
        {/* Full lockup as one inline SVG (train + rail + wordmark + endstop), lifted
            verbatim from design/logo/onestopeurope-lockup-A1.svg. Wordmark stays live
            text so it uses the page's Barlow @font-face. */}
        <svg className="header-logo" viewBox="0 0 600 100" role="img" aria-label="onestopeurope">
          <line x1="-0.271" y1="80.491" x2="473.587" y2="80.491" fill="none" stroke="#ffffff" strokeWidth="2.93228" strokeLinecap="round" />
          <circle cx="479.908" cy="80.375" r="5" fill="#003399" stroke="#ffffff" strokeWidth="3" />
          <path d="M38 80 V46 Q38 36 48 36 H118 Q136 36 146 50 L156 68 Q160 76 152 80 Z" fill="none" stroke="#ffffff" strokeWidth="4" strokeLinejoin="round" />
          <circle cx="65.356" cy="79.874" r="4" fill="#003399" stroke="#ffffff" strokeWidth="3" />
          <circle cx="119.736" cy="79.887" r="4" fill="#003399" stroke="#ffffff" strokeWidth="3" />
          <circle cx="122" cy="52" r="2.4" fill="#ffffff" />
          <circle cx="136" cy="56" r="2.4" fill="#ffffff" />
          <path d="M124 62 Q130 66 135 61" fill="none" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" />
          <path d="M48 46 H100" fill="none" stroke="#ffffff" strokeWidth="2.2" strokeDasharray="1 7" strokeLinecap="round" />
          <text x="84.424" y="70" fontSize="16" fill="#ffcc00">★</text>
          <text x="182" y="79.226" fontFamily="Barlow, sans-serif" fontWeight="700" fontSize="40">
            <tspan fill="#ffffff">onestop</tspan><tspan fill="#ffcc00">europe</tspan>
          </text>
        </svg>
        <span className="header-tagline">nonstopeurope with onestopeurope</span>
        <button className="theme-toggle" onClick={toggleTheme}
                aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}>
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </header>
      <JourneyPlanner
        reach={reach} stationsById={stationsById}
        origin={origin} destination={destination} dest={dest}
        maxTrains={maxTrains} maxMinutes={maxMinutes} filterMinutes={filterMinutes}
        armed={armed} error={error} hint={hint}
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
