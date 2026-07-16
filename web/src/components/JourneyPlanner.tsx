import { useCallback, useRef, type ReactNode } from "react";
import StationField from "./StationField";
import TripDetails from "./TripDetails";
import StopToggle from "./StopToggle";
import TimeSlider from "./TimeSlider";
import { api } from "../lib/api";
import type { CityLookup } from "../lib/cities";
import { cityOptions, destOptions, swapEnabled, toEnabled, toFieldOptions } from "../lib/planner";
import type { MaxTrains } from "../lib/geojson";
import type { CityGroups, Destination, ReachFile, Station } from "../lib/types";
import type { FieldOption } from "../lib/planner";
import { sheetStateAfterGesture, type SheetState } from "../lib/mobileLayout";

interface Props {
  reach: ReachFile | null;
  stationsById: Map<string, Station>;
  cities: CityLookup;
  cityGroups: CityGroups;
  originLabel?: string;
  origin?: Station;
  destination?: Station;
  dest?: Destination;
  maxTrains: MaxTrains;
  maxMinutes: number;
  filterMinutes: number; // effective time cap (Infinity at "max") for To results
  armed: "from" | "to"; // which field the next map click fills — always highlighted
  onSetOrigin: (option: FieldOption) => void;
  onClearOrigin: () => void;
  onSetDest: (s: Station) => void;
  onClearDest: () => void;
  onSwap: () => void;
  onArm: (f: "from" | "to") => void;
  onMaxTrains: (v: MaxTrains) => void;
  onMaxMinutes: (v: number) => void;
  mobile: boolean;
  sheetState: SheetState;
  collapsedSummary: string | null;
  header: ReactNode;
  onSheetStateChange: (state: SheetState) => void;
}

export default function JourneyPlanner(props: Props) {
  const {
    reach, stationsById, cities, cityGroups, origin, originLabel, destination, dest,
    maxTrains, maxMinutes, filterMinutes, armed,
  } = props;
  const gestureStartY = useRef<number | null>(null);
  const suppressClick = useRef(false);
  const collapsed = props.mobile && props.sheetState === "collapsed";

  const searchFrom = useCallback(
    (q: string) => api.searchStations(q).then((r) => [
      ...cityOptions(cityGroups, q),
      ...toFieldOptions(r.stations),
    ]),
    [cityGroups],
  );
  const searchTo = useCallback(
    (q: string) => destOptions(reach, stationsById, q, filterMinutes, cities),
    [reach, stationsById, filterMinutes, cities],
  );

  return (
    <aside className={`panel planner${props.mobile ? ` sheet-${props.sheetState}` : ""}`}>
      {props.mobile && (
        <button
          type="button"
          className="sheet-handle"
          aria-expanded={props.sheetState === "expanded"}
          aria-controls="planner-sheet-content"
          aria-label={props.sheetState === "collapsed" ? "Expand journey planner" : "Collapse journey planner"}
          onPointerDown={(event) => {
            gestureStartY.current = event.clientY;
          }}
          onPointerUp={(event) => {
            if (gestureStartY.current === null) return;
            props.onSheetStateChange(
              sheetStateAfterGesture(props.sheetState, gestureStartY.current, event.clientY),
            );
            gestureStartY.current = null;
            suppressClick.current = true;
          }}
          onClick={() => {
            if (suppressClick.current) {
              suppressClick.current = false;
              return;
            }
            props.onSheetStateChange(props.sheetState === "collapsed" ? "expanded" : "collapsed");
          }}
        >
          <span className="sheet-handle-pill" aria-hidden="true" />
          <span className="sheet-handle-arrow" aria-hidden="true">⌃</span>
        </button>
      )}
      <div className="sheet-header" hidden={collapsed}>{props.header}</div>
      <div className="planner-fields">
        <span className="fields-gutter" aria-hidden="true" hidden={collapsed} />
        <StationField
          placeholder="Start from…"
          armed={armed === "from"}
          value={originLabel ?? origin?.name ?? ""}
          search={searchFrom}
          onPick={props.onSetOrigin}
          onClear={props.onClearOrigin}
          onFocusField={() => props.onArm("from")}
          hidden={collapsed && armed !== "from"}
        />
        <button className="swap-btn" onClick={props.onSwap}
                disabled={!swapEnabled(!!origin, !!destination)}
                aria-label="Swap From and To" hidden={collapsed}>⇄</button>
        <StationField
          placeholder="To… (or click the map)"
          disabled={!toEnabled(!!origin)}
          armed={armed === "to"}
          value={destination?.name ?? ""}
          search={searchTo}
          onPick={(option) => {
            if (option.kind === "station") props.onSetDest(option.station);
          }}
          onClear={props.onClearDest}
          onFocusField={() => props.onArm("to")}
          hidden={collapsed && armed !== "to"}
        />
      </div>

      {collapsed && props.collapsedSummary && (
        <p role="status" className="sheet-context" title={props.collapsedSummary}>
          {props.collapsedSummary}
        </p>
      )}

      <div id="planner-sheet-content" hidden={collapsed}>
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
      </div>

    </aside>
  );
}
