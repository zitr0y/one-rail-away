import { describe, expect, it } from "vitest";
import { overlapStationChoices } from "./overlap";
import type { Station } from "./types";

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
