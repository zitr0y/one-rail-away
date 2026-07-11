import { describe, expect, it } from "vitest";
import { bestJourney, chaikin, destinationsGeoJSON, linesGeoJSON, timeBucket } from "./geojson";
import type { ReachFile, Station } from "./types";

const S = (id: string, lon: number): Station =>
  ({ id, name: id, lat: 50, lon, country: "XX", has_reach: true });
const stationsById = new Map(["A", "B", "C", "D"].map((id, i) => [id, S(id, 8 + i)]));

const reach: ReachFile = {
  origin: "A", computed_at: "", sample_date: "2026-07-14",
  destinations: [
    { id: "C", direct_per_day: 1, journeys: [
      { trains: 1, duration_min: 120, legs: [{ train: "IC 100", dep: "08:00", arr: "10:00", from: "A", to: "C", via: ["B"] }] } ] },
    { id: "D", direct_per_day: 0, journeys: [
      { trains: 2, duration_min: 240, legs: [
        { train: "IC 100", dep: "08:00", arr: "10:00", from: "A", to: "C", via: ["B"] },
        { train: "TGV 10", dep: "10:30", arr: "12:00", from: "C", to: "D", via: [] } ] } ] },
  ],
};

describe("bestJourney / timeBucket", () => {
  it("respects the train budget", () => {
    expect(bestJourney(reach.destinations[1], 1)).toBeNull();
    expect(bestJourney(reach.destinations[1], 2)?.duration_min).toBe(240);
  });
  it("buckets by duration", () => {
    expect([timeBucket(100), timeBucket(200), timeBucket(400), timeBucket(700)]).toEqual([0, 1, 2, 3]);
  });
});

describe("geojson builders", () => {
  it("nonstop view hides multi-train destinations", () => {
    const fc = destinationsGeoJSON(reach, stationsById, 1, Infinity);
    expect(fc.features.map((f) => f.properties.id)).toEqual(["C"]);
  });
  it("carries n_routes for reach-dot sizing, defaulting to 0", () => {
    const fc = destinationsGeoJSON(reach, stationsById, 3, Infinity);
    for (const f of fc.features) expect(f.properties.n_routes).toBe(0);
  });
  it("max-minutes filter applies", () => {
    const fc = destinationsGeoJSON(reach, stationsById, 3, 130);
    expect(fc.features.map((f) => f.properties.id)).toEqual(["C"]);
  });
  it("lines pass through via and transfer stations", () => {
    const fc = linesGeoJSON(reach, stationsById, 3, Infinity);
    const d = fc.features.find((f) => f.properties.id === "D")!;
    const lons = (d.geometry.coordinates as [number, number][]).map(([lon]) => lon);
    expect(lons[0]).toBe(8);                       // origin A preserved
    expect(lons[lons.length - 1]).toBe(11);        // dest D preserved
    expect(Math.max(...lons)).toBe(11);            // monotone-ish through B(9), C(10)
  });
});

describe("chaikin", () => {
  it("preserves endpoints and adds points", () => {
    const input: [number, number][] = [[0, 0], [1, 1], [2, 0]];
    const out = chaikin(input, 2);
    expect(out[0]).toEqual([0, 0]);
    expect(out[out.length - 1]).toEqual([2, 0]);
    expect(out.length).toBeGreaterThan(input.length);
  });
});

describe("linesGeoJSON per-leg smoothing", () => {
  // Barcelona(A) -> Paris(B) -> Sens(C), where leg 2 doubles back near A: whole-line
  // chaikin rounds the Paris corner into a U-curve whose apex lands ~100km short of
  // Paris, over empty countryside near Auxerre (user report 2026-07-09). Smoothing
  // each leg separately keeps B a sharp vertex the line visibly passes through.
  const hairpinStations = new Map<string, Station>([
    ["A", { id: "A", name: "A", lat: 41, lon: 2, country: "XX", has_reach: true }],
    ["B", { id: "B", name: "B", lat: 49, lon: 2.3, country: "XX", has_reach: true }],
    ["C", { id: "C", name: "C", lat: 48, lon: 3.3, country: "XX", has_reach: true }],
  ]);
  const hairpinReach: ReachFile = {
    origin: "A", computed_at: "", sample_date: "2026-07-14",
    destinations: [
      { id: "C", direct_per_day: 0, journeys: [
        { trains: 2, duration_min: 300, legs: [
          { train: "AVE 100", dep: "08:00", arr: "13:00", from: "A", to: "B", via: [] },
          { train: "TER 20", dep: "13:30", arr: "15:00", from: "B", to: "C", via: [] } ] } ] },
    ],
  };

  it("keeps the transfer station as an exact vertex and preserves line endpoints", () => {
    const fc = linesGeoJSON(hairpinReach, hairpinStations, 3, Infinity);
    const feature = fc.features.find((f) => f.properties.id === "C")!;
    const coords = feature.geometry.coordinates as [number, number][];
    const b = hairpinStations.get("B")!;
    const a = hairpinStations.get("A")!;
    const c = hairpinStations.get("C")!;
    expect(coords).toContainEqual([b.lon, b.lat]);
    expect(coords[0]).toEqual([a.lon, a.lat]);
    expect(coords[coords.length - 1]).toEqual([c.lon, c.lat]);
  });

  it("matches a direct chaikin call for single-leg journeys (regression guard)", () => {
    const fc = linesGeoJSON(reach, stationsById, 1, Infinity);
    const feature = fc.features.find((f) => f.properties.id === "C")!;
    const a = stationsById.get("A")!;
    const b = stationsById.get("B")!;
    const c = stationsById.get("C")!;
    const expected = chaikin([[a.lon, a.lat], [b.lon, b.lat], [c.lon, c.lat]], 2);
    expect(feature.geometry.coordinates).toEqual(expected);
  });
});
