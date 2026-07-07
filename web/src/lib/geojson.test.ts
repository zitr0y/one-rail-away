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
