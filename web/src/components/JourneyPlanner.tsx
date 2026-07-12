import { useCallback } from "react";
import StationField from "./StationField";
import TripDetails from "./TripDetails";
import StopToggle from "./StopToggle";
import TimeSlider from "./TimeSlider";
import { api } from "../lib/api";
import { reachableDestOptions, swapEnabled, toEnabled } from "../lib/planner";
import type { MaxTrains } from "../lib/geojson";
import type { Destination, ReachFile, Station } from "../lib/types";

interface Props {
  reach: ReachFile | null;
  stationsById: Map<string, Station>;
  origin?: Station;
  destination?: Station;
  dest?: Destination;
  maxTrains: MaxTrains;
  maxMinutes: number;
  armed: "from" | "to"; // which field the next map click fills — always highlighted
  error: string | null;
  hint: string | null;
  onSetOrigin: (s: Station) => void;
  onClearOrigin: () => void;
  onSetDest: (s: Station) => void;
  onClearDest: () => void;
  onSwap: () => void;
  onArm: (f: "from" | "to") => void;
  onMaxTrains: (v: MaxTrains) => void;
  onMaxMinutes: (v: number) => void;
}

export default function JourneyPlanner(props: Props) {
  const { reach, stationsById, origin, destination, dest, maxTrains, maxMinutes, armed, error, hint } = props;

  const searchFrom = useCallback(
    (q: string) => api.searchStations(q).then((r) => r.stations),
    [],
  );
  const searchTo = useCallback(
    (q: string) => reachableDestOptions(reach, stationsById, q),
    [reach, stationsById],
  );

  return (
    <aside className="panel planner">
      <div className="planner-fields">
        <span className="fields-gutter" aria-hidden="true" />
        <StationField
          placeholder="Start from…"
          armed={armed === "from"}
          value={origin?.name ?? ""}
          search={searchFrom}
          onPick={props.onSetOrigin}
          onClear={props.onClearOrigin}
          onFocusField={() => props.onArm("from")}
        />
        <button className="swap-btn" onClick={props.onSwap}
                disabled={!swapEnabled(!!origin, !!destination)}
                aria-label="Swap From and To">⇄</button>
        <StationField
          placeholder="To… (or click the map)"
          disabled={!toEnabled(!!origin)}
          armed={armed === "to"}
          value={destination?.name ?? ""}
          search={searchTo}
          onPick={props.onSetDest}
          onClear={props.onClearDest}
          onFocusField={() => props.onArm("to")}
        />
      </div>

      <div className="planner-divider" />
      <StopToggle value={maxTrains} onChange={props.onMaxTrains} />
      <TimeSlider value={maxMinutes} onChange={props.onMaxMinutes} />

      {origin && destination && dest && (
        <>
          <div className="planner-divider" />
          <TripDetails origin={origin} destination={destination} dest={dest}
                       maxTrains={maxTrains} stationsById={stationsById} />
        </>
      )}

      {hint && <p className="hint">{hint}</p>}
      {!reach && <p className="hint">Search or click a station to begin.</p>}
      {error && <p className="error">{error}</p>}
    </aside>
  );
}
