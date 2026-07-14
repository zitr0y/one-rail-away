import { describe, expect, it } from "vitest";
import {
  overlapStationChoices, rankTargetChoices, reachableMinTrains, type StationChoice,
} from "./overlap";
import type { ReachFile, Station } from "./types";

const stations = [
  { id: "b", name: "Beta", lon: 8, lat: 50, n_dest: 20 },
  { id: "a", name: "Alpha", lon: 8, lat: 50, n_dest: 50 },
  { id: "a2", name: "alpha", lon: 8, lat: 50, n_dest: 50 },
] as Station[];

describe("overlapStationChoices", () => {
  it("collects visible stations once and keeps normal layer priority per station", () => {
    expect(overlapStationChoices([
      { layer: "all-stations", id: "b" },
      { layer: "reach-dots", id: "b" },
      { layer: "all-stations", id: "a" },
    ], stations)).toEqual([
      { name: "Alpha", nDest: 50, pick: { type: "origin", id: "a" } },
      { name: "Beta", nDest: 20, pick: { type: "dest", id: "b" } },
    ]);
  });

  it("orders choices by connection count, then deterministically by name and id", () => {
    expect(overlapStationChoices([
      { layer: "all-stations", id: "b" },
      { layer: "all-stations", id: "a2" },
      { layer: "all-stations", id: "a" },
    ], stations).map((choice) => choice.pick.id)).toEqual(["a", "a2", "b"]);
  });

  it("leaves a lone hit as one direct-selectable choice, while overlaps have several", () => {
    expect(overlapStationChoices([{ layer: "all-stations", id: "a" }], stations)).toHaveLength(1);
    expect(overlapStationChoices([
      { layer: "all-stations", id: "a" },
      { layer: "all-stations", id: "b" },
    ], stations)).toHaveLength(2);
  });
});

const choice = (id: string, name: string, nDest: number): StationChoice =>
  ({ pick: { type: "dest", id }, name, nDest });

describe("reachableMinTrains", () => {
  const reach = {
    origin: "o", computed_at: "", sample_date: "",
    destinations: [
      { id: "d1", direct_per_day: 1, journeys: [
        { trains: 2, duration_min: 100, legs: [] },
        { trains: 3, duration_min: 80, legs: [] },   // faster but more trains
      ]},
      { id: "d2", direct_per_day: 1, journeys: [
        { trains: 1, duration_min: 999, legs: [] },  // over the time filter
      ]},
    ],
  } as ReachFile;

  it("returns the FEWEST trains among journeys within both filters", () => {
    expect(reachableMinTrains(reach, 3, 200).get("d1")).toBe(2);
  });

  it("excludes destinations outside the time or trains filter", () => {
    expect(reachableMinTrains(reach, 3, 200).has("d2")).toBe(false);
    expect(reachableMinTrains(reach, 1, 200).has("d1")).toBe(false);
  });

  it("is empty without a reach", () => {
    expect(reachableMinTrains(null, 3, 200).size).toBe(0);
  });
});

describe("rankTargetChoices", () => {
  it("orders reachable by fewest trains, then size; unreachable last", () => {
    const ranked = rankTargetChoices(
      [choice("far", "Far", 90), choice("near", "Near", 10),
       choice("none", "None", 99), choice("big", "Big", 80)],
      new Map([["far", 2], ["near", 1], ["big", 1]]),
    );
    expect(ranked.map((c) => c.pick.id)).toEqual(["big", "near", "far", "none"]);
    expect(ranked[3].minTrains).toBeNull();
  });

  it("breaks full ties by name then id", () => {
    const ranked = rankTargetChoices(
      [choice("b", "Same", 5), choice("a", "Same", 5)],
      new Map([["a", 1], ["b", 1]]),
    );
    expect(ranked.map((c) => c.pick.id)).toEqual(["a", "b"]);
  });
});
