import { describe, expect, it } from "vitest";
import type { StyleSpecification } from "maplibre-gl";
import { mergeCustomStyle } from "./themeswap";

function fakePrevious(): StyleSpecification {
  return {
    version: 8,
    sources: {
      openmaptiles: { type: "vector", url: "https://old-basemap" },
      "all-stations": { type: "geojson", data: { type: "FeatureCollection", features: [] } },
      "reach-lines": { type: "geojson", data: { type: "FeatureCollection", features: [] } },
      "transfer-points": { type: "geojson", data: { type: "FeatureCollection", features: [] } },
      "reach-dots": { type: "geojson", data: { type: "FeatureCollection", features: [] } },
      coverage: { type: "geojson", data: { type: "FeatureCollection", features: [] } },
      capitals: { type: "geojson", data: { type: "FeatureCollection", features: [] } },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#F2EFE9" } },
      { id: "coverage-veil", type: "fill", source: "coverage",
        paint: { "fill-color": "#9c9589", "fill-opacity": 0.5 } },
      { id: "reach-lines", type: "line", source: "reach-lines", paint: { "line-opacity": 0.05 } },
      { id: "reach-lines-selected", type: "line", source: "reach-lines", paint: {} },
      { id: "all-stations", type: "circle", source: "all-stations",
        paint: { "circle-color": "#003399", "circle-opacity": 0.25 } },
      { id: "reach-dots", type: "circle", source: "reach-dots",
        paint: { "circle-stroke-color": "#F2EFE9" } },
      { id: "capital-stars", type: "symbol", source: "capitals", layout: {} },
      { id: "transfer-points", type: "symbol", source: "transfer-points",
        layout: { "icon-image": "stop-sign-icon", "icon-allow-overlap": true } },
    ],
  } as StyleSpecification;
}

function fakeNext(): StyleSpecification {
  return {
    version: 8,
    sources: { openmaptiles: { type: "vector", url: "https://new-basemap" } },
    layers: [{ id: "background", type: "background", paint: { "background-color": "#101C36" } }],
  } as StyleSpecification;
}

describe("mergeCustomStyle", () => {
  it("returns next unchanged when previous is undefined (initial load)", () => {
    const next = fakeNext();
    expect(mergeCustomStyle(undefined, next, "dark")).toBe(next);
  });

  it("carries the six custom sources; basemap sources come from next", () => {
    const merged = mergeCustomStyle(fakePrevious(), fakeNext(), "dark");
    for (const id of ["all-stations", "reach-lines", "transfer-points", "reach-dots", "coverage", "capitals"]) {
      expect(merged.sources[id]).toBeDefined();
    }
    expect((merged.sources.openmaptiles as { url: string }).url).toBe("https://new-basemap");
  });

  it("appends the seven custom layers after the basemap layers, in order", () => {
    const merged = mergeCustomStyle(fakePrevious(), fakeNext(), "dark");
    expect(merged.layers.map((l) => l.id)).toEqual([
      "background", "coverage-veil", "reach-lines", "reach-lines-selected",
      "all-stations", "reach-dots", "capital-stars", "transfer-points",
    ]);
  });

  it("re-tints theme-dependent paints and keeps live paint state", () => {
    const merged = mergeCustomStyle(fakePrevious(), fakeNext(), "dark");
    const byId = new Map(merged.layers.map((l) => [l.id, l]));
    const stations = byId.get("all-stations") as { paint: Record<string, unknown> };
    expect(stations.paint["circle-color"]).toBe("#5B7FDB");
    expect(stations.paint["circle-opacity"]).toBe(0.25); // live value carried, not reset
    const veil = byId.get("coverage-veil") as { paint: Record<string, unknown> };
    expect(veil.paint["fill-color"]).toBe("#6B7590");
    expect(veil.paint["fill-opacity"]).toBe(0.5);
    const dots = byId.get("reach-dots") as { paint: Record<string, unknown> };
    expect(dots.paint["circle-stroke-color"]).toBe("#101C36");
    // transfer-points is a fixed-colour stop-sign symbol; carried across the
    // swap without retinting, its icon layout preserved.
    const transfers = byId.get("transfer-points") as { layout: Record<string, unknown> };
    expect(transfers.layout["icon-image"]).toBe("stop-sign-icon");
  });

  it("light theme re-tints back to light values", () => {
    const merged = mergeCustomStyle(fakePrevious(), fakeNext(), "light");
    const stations = merged.layers.find((l) => l.id === "all-stations") as
      { paint: Record<string, unknown> };
    expect(stations.paint["circle-color"]).toBe("#003399");
  });
});
