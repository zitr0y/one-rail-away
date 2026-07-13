import { useCallback, useEffect, useMemo, useState } from "react";
import { emptyClickAction, swapDest } from "./lib/selection";
import { armedTarget, routeMapClick, type ActiveField } from "./lib/mapclick";
import MapView from "./components/Map";
import JourneyPlanner from "./components/JourneyPlanner";
import { TIME_MAX } from "./components/TimeSlider";
import { api } from "./lib/api";
import { buildCityLookup } from "./lib/cities";
import { unionReach } from "./lib/cityunion";
import type { MaxTrains } from "./lib/geojson";
import type { FeaturePick } from "./lib/pickfeature";
import type { CityGroups, ReachFile, Station } from "./lib/types";
import { useTheme } from "./lib/theme";
import headerLogo from "./assets/header-logo.svg?raw";

export default function App() {
  const [stations, setStations] = useState<Station[]>([]);
  const [cityGroups, setCityGroups] = useState<CityGroups>({});
  const [cityOrigin, setCityOrigin] = useState<{ city: string; memberIds: string[] } | null>(null);
  const [reach, setReach] = useState<ReachFile | null>(null);
  const [maxTrains, setMaxTrains] = useState<MaxTrains>(1);
  const [maxMinutes, setMaxMinutes] = useState(TIME_MAX); // start at "max" (no cap)
  const [selectedDest, setSelectedDest] = useState<string | null>(null);
  const [activeField, setActiveField] = useState<ActiveField>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, toggleTheme] = useTheme();

  const stationsById = useMemo(() => new Map(stations.map((s) => [s.id, s])), [stations]);
  const cities = useMemo(() => buildCityLookup(cityGroups), [cityGroups]);

  useEffect(() => {
    api.getStations().then((r) => setStations(r.stations)).catch((e) => setError(String(e)));
    api.getCities().then(setCityGroups).catch(() => setCityGroups({}));
  }, []);

  const selectOrigin = useCallback((id: string) => {
    setCityOrigin(null);
    setSelectedDest(null);
    setHint(null);
    setActiveField("to"); // auto-advance arming to To
    api.getReach(id).then(setReach).catch((e) => setError(String(e)));
  }, []);

  const selectCityOrigin = useCallback(async (city: string, memberIds: string[]) => {
    setCityOrigin({ city, memberIds });
    setSelectedDest(null);
    setHint(null);
    setActiveField("to");
    try {
      const results = await Promise.allSettled(memberIds.map((id) => api.getReach(id)));
      const reaches = results.flatMap((result) =>
        result.status === "fulfilled" ? [result.value] : [],
      );
      if (reaches.length === 0) throw new Error(`No reach data for ${city}`);
      setReach(unionReach(reaches));
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const clearSelection = useCallback(() => {
    setCityOrigin(null);
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
    setCityOrigin(null);
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
        {/* Brand lockup — edit web/src/assets/header-logo.svg in Inkscape; it is
            inlined here (Vite ?raw) so the wordmark uses the page's Barlow font. */}
        <span className="header-logo" role="img" aria-label="onestopeurope"
              dangerouslySetInnerHTML={{ __html: headerLogo }} />
        <span className="header-tagline">nonstopeurope with onestopeurope</span>
        <button className="theme-toggle" onClick={toggleTheme}
                aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}>
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </header>
      <JourneyPlanner
        reach={reach} stationsById={stationsById}
        cities={cities} cityGroups={cityGroups} originLabel={cityOrigin?.city}
        origin={origin} destination={destination} dest={dest}
        maxTrains={maxTrains} maxMinutes={maxMinutes} filterMinutes={filterMinutes}
        armed={armed} error={error} hint={hint}
        onSetOrigin={(option) => {
          if (option.kind === "city") selectCityOrigin(option.city, option.memberIds);
          else selectOrigin(option.station.id);
        }}
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
