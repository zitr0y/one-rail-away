import { describe, expect, it } from "vitest";
import { buildSmoothedLookup, expandHops, smoothedLookupFor, stationTangents } from "./smoothPaths";
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

const norm = ([x, y]: [number, number]): [number, number] => {
  const l = Math.hypot(x, y);
  return [x / l, y / l];
};

describe("buildSmoothedLookup", () => {
  // Gentle east-west line with a slight bend at B, near the equator so
  // lon/lat distances are near-planar and the assertions stay readable.
  const bent = new Map([S("A", 0, 0), S("B", 2, 0.5), S("C", 4, 0)]);
  const bentReach = reachOf([journey(leg("A", "C", ["B"]))]);

  it("station coordinates are the exact first/last curve vertices", () => {
    const lookup = buildSmoothedLookup(bentReach, bent);
    const ab = lookup.get("A|B")!;
    expect(ab.fwd[0]).toEqual([0, 0]);
    expect(ab.fwd[ab.fwd.length - 1]).toEqual([2, 0.5]);
    expect(ab.rev[0]).toEqual([2, 0.5]);
    expect(ab.rev[ab.rev.length - 1]).toEqual([0, 0]);
  });

  it("a shared hop has exactly one geometry, independent of journey order", () => {
    const twoJourneys = reachOf([journey(leg("A", "B"))], [journey(leg("A", "C", ["B"]))]);
    const reordered = reachOf([journey(leg("A", "C", ["B"]))], [journey(leg("A", "B"))]);
    const l1 = buildSmoothedLookup(twoJourneys, bent);
    const l2 = buildSmoothedLookup(reordered, bent);
    expect(l1.size).toBe(2);
    expect(Object.fromEntries(l1)).toEqual(Object.fromEntries(l2));
  });

  it("curves join collinearly at a through station (no kink at B)", () => {
    const lookup = buildSmoothedLookup(bentReach, bent);
    const into = lookup.get("A|B")!.fwd; // oriented A→B
    const out = lookup.get("B|C")!.fwd;  // oriented B→C
    const [x1, y1] = into[into.length - 2];
    const u = norm([2 - x1, 0.5 - y1]); // arrival direction at B
    const [x2, y2] = out[1];
    const v = norm([x2 - 2, y2 - 0.5]); // departure direction from B
    expect(u[0] * v[0] + u[1] * v[1]).toBeGreaterThan(0.99);
  });

  it("an isolated two-point hop degenerates to a straight line", () => {
    const pair = new Map([S("A", 0, 0), S("B", 2, 0)]); // horizontal, ~222 km
    const lookup = buildSmoothedLookup(reachOf([journey(leg("A", "B"))]), pair);
    const fwd = lookup.get("A|B")!.fwd;
    expect(fwd.length).toBeGreaterThanOrEqual(8); // MIN_POINTS floor
    for (const [, y] of fwd) expect(y).toBe(0);   // exactly on the line
  });

  it("a filtered subset would produce different geometry — full file required", () => {
    // With only the A→B journey, B is degree-1 and A|B is straight; the full
    // file's A→C-via-B journey pulls B's tangent onto the through-axis. This
    // is WHY the lookup must always come from the full reach file.
    const full = reachOf([journey(leg("A", "B"))], [journey(leg("A", "C", ["B"]))]);
    const subset = reachOf([journey(leg("A", "B"))]);
    const fullLookup = buildSmoothedLookup(full, bent);
    const subsetLookup = buildSmoothedLookup(subset, bent);
    expect(fullLookup.get("A|B")!.fwd).not.toEqual(subsetLookup.get("A|B")!.fwd);
  });

  it("transfer legs contribute no geometry", () => {
    const stations = new Map([S("A", 0, 0), S("B", 1, 0), S("X", 1.01, 0.01), S("C", 2, 0)]);
    const withTransfer = reachOf([journey(
      leg("A", "B"),
      { type: "transfer", mode: "walk", minutes: 10, from_id: "B", to_id: "X" },
      leg("X", "C"),
    )]);
    const lookup = buildSmoothedLookup(withTransfer, stations);
    expect([...lookup.keys()].sort()).toEqual(["A|B", "C|X"]);
  });

  it("hops with a station missing from byId are absent (straight fallback)", () => {
    const stations = new Map([S("A", 0, 0), S("B", 1, 0)]); // C unknown
    const lookup = buildSmoothedLookup(reachOf([journey(leg("A", "C", ["B"]))]), stations);
    expect(lookup.has("A|B")).toBe(true);
    expect(lookup.has("B|C")).toBe(false);
  });

  it("malformed reach file yields an empty lookup, never a throw", () => {
    expect(buildSmoothedLookup({} as ReachFile, new Map()).size).toBe(0);
  });
});

describe("smoothedLookupFor memoization", () => {
  it("returns the same Map instance for the same reach file + stations", () => {
    const stations = new Map([S("A", 0, 0), S("B", 1, 0)]);
    const reach = reachOf([journey(leg("A", "B"))]);
    const first = smoothedLookupFor(reach, stations);
    expect(smoothedLookupFor(reach, stations)).toBe(first);
    // A new reach identity (e.g. a re-fetch) recomputes.
    expect(smoothedLookupFor(reachOf([journey(leg("A", "B"))]), stations)).not.toBe(first);
  });
});
