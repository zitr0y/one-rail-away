import { describe, expect, it } from "vitest";
import { reachableDestOptions, swapEnabled, toEnabled } from "./planner";
import type { ReachFile, Station } from "./types";

const st = (id: string, name: string): Station => ({
  id, name, lat: 0, lon: 0, country: "DE", has_reach: true,
});

const stationsById = new Map<string, Station>([
  ["p", st("p", "Paris Nord")],
  ["b", st("b", "Brussels Midi")],
  ["k", st("k", "Köln Hbf")], // in the map but NOT a destination of this origin
]);

const reach: ReachFile = {
  origin: "o", computed_at: "", sample_date: "",
  destinations: [
    { id: "p", direct_per_day: 3, journeys: [] },
    { id: "b", direct_per_day: 5, journeys: [] },
  ],
};

describe("reachableDestOptions", () => {
  it("returns reachable destinations whose name matches the query", () => {
    expect(reachableDestOptions(reach, stationsById, "par").map((s) => s.id)).toEqual(["p"]);
  });
  it("matches case-insensitively on a substring", () => {
    expect(reachableDestOptions(reach, stationsById, "MIDI").map((s) => s.id)).toEqual(["b"]);
  });
  it("never offers a station that is not in the reach set", () => {
    expect(reachableDestOptions(reach, stationsById, "köln")).toEqual([]);
  });
  it("is empty for a short query or when there is no reach", () => {
    expect(reachableDestOptions(reach, stationsById, "p")).toEqual([]);
    expect(reachableDestOptions(null, stationsById, "paris")).toEqual([]);
  });
  it("respects the limit", () => {
    const many = new Map<string, Station>([
      ["a", st("a", "Anytown Central")],
      ["b", st("b", "Anytown East")],
      ["c", st("c", "Anytown West")],
    ]);
    const big: ReachFile = {
      origin: "o", computed_at: "", sample_date: "",
      destinations: [
        { id: "a", direct_per_day: 1, journeys: [] },
        { id: "b", direct_per_day: 1, journeys: [] },
        { id: "c", direct_per_day: 1, journeys: [] },
      ],
    };
    expect(reachableDestOptions(big, many, "anytown", 2)).toHaveLength(2);
  });
});

describe("swapEnabled / toEnabled", () => {
  it("swap needs both endpoints", () => {
    expect(swapEnabled(true, true)).toBe(true);
    expect(swapEnabled(true, false)).toBe(false);
    expect(swapEnabled(false, true)).toBe(false);
  });
  it("To needs an origin", () => {
    expect(toEnabled(true)).toBe(true);
    expect(toEnabled(false)).toBe(false);
  });
});
