import { describe, expect, it } from "vitest";
import { expandHops, stationTangents } from "./smoothPaths";
import type { Journey, JourneyLeg, ReachFile, Station } from "./types";

const S = (id: string, lon: number, lat: number): [string, Station] =>
  [id, { id, name: id, lon, lat, country: "XX", has_reach: true }];

const leg = (from: string, to: string, via: string[] = []): JourneyLeg =>
  ({ train: "ICE 1", dep: "08:00", arr: "09:00", from, to, via });

const journey = (...legs: JourneyLeg[]): Journey =>
  ({ trains: legs.length, duration_min: 60, legs });

/** One destination per journey list — enough shape for the geometry code. */
const reachOf = (...journeyLists: Journey[][]): ReachFile => ({
  origin: "A", computed_at: "", sample_date: "2026-07-14",
  destinations: journeyLists.map((journeys, i) => ({
    id: `dest${i}`, direct_per_day: 1, journeys,
  })),
});

describe("expandHops", () => {
  it("expands [from, ...via, to] into weighted consecutive hops", () => {
    const hops = expandHops(reachOf([journey(leg("A", "C", ["B"]))]));
    expect([...hops.keys()].sort()).toEqual(["A|B", "B|C"]);
    expect(hops.get("A|B")).toEqual({ a: "A", b: "B", weight: 1 });
  });

  it("accumulates weight per traversal and direction-normalizes the key", () => {
    const hops = expandHops(reachOf(
      [journey(leg("A", "C", ["B"]))],
      [journey(leg("C", "A", ["B"]))], // opposite direction, same physical hops
    ));
    expect(hops.size).toBe(2);
    expect(hops.get("A|B")!.weight).toBe(2);
    expect(hops.get("B|C")!.weight).toBe(2);
  });

  it("skips transfer legs", () => {
    const transfer: JourneyLeg =
      { type: "transfer", mode: "walk", minutes: 10, from_id: "B", to_id: "X" };
    const hops = expandHops(reachOf([journey(leg("A", "B"), transfer, leg("X", "C"))]));
    expect([...hops.keys()].sort()).toEqual(["A|B", "C|X"]);
  });

  it("drops zero-length hops from repeated consecutive stop ids", () => {
    const hops = expandHops(reachOf([journey(leg("A", "B", ["A"]))]));
    expect([...hops.keys()]).toEqual(["A|B"]);
  });

  it("returns an empty map for a malformed reach file instead of throwing", () => {
    expect(expandHops({} as ReachFile).size).toBe(0);
    expect(expandHops(null as unknown as ReachFile).size).toBe(0);
  });
});

describe("stationTangents", () => {
  // Collinear east-west line at lat 50 — directions must be angle-true even
  // though a lon-degree is only cos(50°) of a lat-degree here.
  const line = new Map([S("A", 8, 50), S("B", 9, 50), S("C", 10, 50)]);

  it("degree-1 station: tangent is its single hop's direction", () => {
    const hops = expandHops(reachOf([journey(leg("A", "B"))]));
    const ta = stationTangents(hops, line).get("A")!;
    expect(Math.abs(ta[0])).toBeCloseTo(1, 6); // along the east-west hop
    expect(ta[1]).toBeCloseTo(0, 6);
  });

  it("degree-2 through-station: tangent is the bisector of the through pair", () => {
    const hops = expandHops(reachOf([journey(leg("A", "C", ["B"]))]));
    const tb = stationTangents(hops, line).get("B")!;
    expect(Math.abs(tb[0])).toBeCloseTo(1, 6);
    expect(tb[1]).toBeCloseTo(0, 6);
  });

  it("weight × straightness picks the dominant through pair over a light branch", () => {
    const stations = new Map([...line, S("D", 9, 51)]); // branch due north of B
    const heavy = journey(leg("A", "C", ["B"]));
    const hops = expandHops(reachOf([heavy], [heavy], [heavy], [journey(leg("B", "D"))]));
    const tb = stationTangents(hops, stations).get("B")!;
    expect(Math.abs(tb[0])).toBeGreaterThan(0.99); // stays on the A–C axis
  });

  it("is independent of journey iteration order", () => {
    const stations = new Map([...line, S("D", 9, 51), S("E", 11, 50.2)]);
    const journeys = [
      journey(leg("A", "C", ["B"])),
      journey(leg("B", "D")),
      journey(leg("A", "E", ["B", "C"])),
    ];
    const forward = reachOf(...journeys.map((j) => [j]));
    const reversed = reachOf(...journeys.map((j) => [j]).reverse());
    const tf = stationTangents(expandHops(forward), stations);
    const tr = stationTangents(expandHops(reversed), stations);
    expect(Object.fromEntries(tf)).toEqual(Object.fromEntries(tr));
  });

  it("ignores hops whose stations are missing from byId", () => {
    const hops = expandHops(reachOf([journey(leg("A", "Z"))])); // Z unknown
    const t = stationTangents(hops, line);
    expect(t.has("Z")).toBe(false);
    expect(t.has("A")).toBe(false); // its only hop was unusable
  });
});
