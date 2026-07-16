// @vitest-environment jsdom
// Regression test for the live-site "no station dots" bug: stations arrive
// from the API BEFORE the map's `load` event (small gzipped JSON vs. remote
// style + glyphs + tiles), so the stations effect no-ops on a null map — the
// load handler must then run the station sync itself or the all-stations and
// capitals sources stay empty forever.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Station } from "../lib/types";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const handlers: Record<string, () => void> = {};
const sources = new Map<string, { setData: ReturnType<typeof vi.fn> }>();

vi.mock("maplibre-gl", () => {
  class FakeMap {
    on(event: string, a: unknown, b?: unknown) {
      if (typeof a === "function") handlers[event] = a as () => void;
      else if (typeof b === "function") handlers[`${event}:${a as string}`] = b as () => void;
      return this;
    }
    once() { return this; }
    addSource(id: string) { sources.set(id, { setData: vi.fn() }); }
    addLayer() {}
    addImage() {}
    hasImage() { return true; }
    getSource(id: string) { return sources.get(id); }
    setFilter() {}
    setPaintProperty() {}
    setStyle() {}
    easeTo() {}
    getCanvas() { return { style: {} }; }
    queryRenderedFeatures() { return []; }
    remove() {}
  }
  class FakePopup {
    setLngLat() { return this; }
    setText() { return this; }
    setDOMContent() { return this; }
    addTo() { return this; }
    remove() { return this; }
  }
  class FakeMarker {
    setLngLat() { return this; }
    setRotation() { return this; }
    addTo() { return this; }
    remove() { return this; }
  }
  return { default: { Map: FakeMap, Popup: FakePopup, Marker: FakeMarker } };
});

vi.mock("../lib/api", () => ({
  api: { getCoverage: () => new Promise(() => {}) },
}));

import MapView from "./Map";

const stations: Station[] = [
  { id: "A", name: "Aachen Hbf", lat: 50.8, lon: 6.1, country: "DE",
    has_reach: true, is_capital: false, n_dest: 12, n_routes: 3 },
  { id: "B", name: "Berlin Hbf", lat: 52.5, lon: 13.4, country: "DE",
    has_reach: true, is_capital: true, n_dest: 400, n_routes: 60 },
] as never;

function renderMap(): Root {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(
      <MapView stations={stations} reach={null} maxTrains={1} maxMinutes={Infinity}
               selectedDest={null} theme="light" cityGroups={{}} armed="from"
               railPaths={null} onStationClick={() => {}}
               onSelectCityOrigin={() => {}} onEmptyClick={() => {}} />,
    );
  });
  return root;
}

describe("MapView station sources", () => {
  afterEach(() => {
    sources.clear();
    for (const key of Object.keys(handlers)) delete handlers[key];
  });

  it("populates station dots when stations arrived before the map loaded", () => {
    const root = renderMap();
    // Stations were already in props when the map finished loading — the
    // per-prop effects all no-oped on a null map ref, so `load` must sync.
    act(() => handlers["load"]());

    const dotCalls = sources.get("all-stations")!.setData.mock.calls;
    const starCalls = sources.get("capitals")!.setData.mock.calls;
    expect(dotCalls.length).toBeGreaterThan(0);
    expect(starCalls.length).toBeGreaterThan(0);
    const dots = dotCalls.at(-1)![0] as { features: unknown[] };
    const stars = starCalls.at(-1)![0] as { features: unknown[] };
    expect(dots.features).toHaveLength(1); // non-capital with reach
    expect(stars.features).toHaveLength(1); // the capital

    act(() => root.unmount());
  });
});
