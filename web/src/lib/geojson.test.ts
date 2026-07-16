import { describe, expect, it } from "vitest";
import {
  bestJourney, buildRailPathLookup, destinationsGeoJSON, frequencyClass, journeyLegPaths,
  legSegments, linesGeoJSON, segmentsGeoJSON, selectedLineGeoJSON, shown, timeBucket,
  transferPoints, type RailPathLookup, initialMaxTrains,
} from "./geojson";
import type { Journey, Leg, ReachFile, Station } from "./types";

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

describe("frequency styling", () => {
  it("marks limited evidence infrequent and keeps legacy files frequent", () => {
    expect(frequencyClass(reach.destinations[0])).toBe("frequent");
    expect(frequencyClass({ ...reach.destinations[0], frequency: {
      sample_days: 8, available_days: 2, direct_days: 2, direct_trips: 2,
      availability: "limited", active_months: ["Jul"],
    } })).toBe("infrequent");
  });
  it("treats a retired availability value (stale reach file) as frequent, not a crash", () => {
    expect(frequencyClass({ ...reach.destinations[0], frequency: {
      sample_days: 8, available_days: 2, direct_days: 2, direct_trips: 2,
      // @ts-expect-error -- old files carry the retired "seasonal_or_limited" value
      availability: "seasonal_or_limited", active_months: ["Jul"],
    } })).toBe("frequent");
  });
});

describe("transferPoints", () => {
  const pointStations = new Map(["A", "B", "C", "D"].map((id, i) => [id, S(id, i)]));
  const leg = (from: string, to: string, via: string[] = []) => ({
    train: "ICE", dep: "08:00", arr: "09:00", from, to, via,
  });

  it("returns no transfer for a one-leg journey, even with a via station", () => {
    const journey: Journey = { trains: 1, duration_min: 60, legs: [leg("A", "C", ["B"])] };
    expect(transferPoints(journey, pointStations)).toEqual([]);
  });

  it("returns the first leg destination for a two-leg journey", () => {
    const journey: Journey = {
      trains: 2, duration_min: 120, legs: [leg("A", "C", ["B"]), leg("C", "D")],
    };
    expect(transferPoints(journey, pointStations)).toEqual([[2, 50]]);
  });

  it("returns transfer boundaries in order for a three-leg journey", () => {
    const journey: Journey = {
      trains: 3, duration_min: 180, legs: [leg("A", "B"), leg("B", "C"), leg("C", "D")],
    };
    expect(transferPoints(journey, pointStations)).toEqual([[1, 50], [2, 50]]);
  });

  it("omits missing transfer stations while retaining later boundaries", () => {
    const journey: Journey = {
      trains: 3, duration_min: 180, legs: [leg("A", "B"), leg("B", "C"), leg("C", "D")],
    };
    const withoutB = new Map(pointStations);
    withoutB.delete("B");
    expect(transferPoints(journey, withoutB)).toEqual([[2, 50]]);
  });

  it("never emits through stops as transfer points", () => {
    const journey: Journey = {
      trains: 2, duration_min: 120, legs: [leg("A", "C", ["B"]), leg("C", "D")],
    };
    expect(transferPoints(journey, pointStations)).not.toContainEqual([1, 50]);
  });
});

describe("geojson builders", () => {
  it("nonstop view hides multi-train destinations", () => {
    const fc = destinationsGeoJSON(shown(reach, 1, Infinity), stationsById);
    expect(fc.features.map((f) => f.properties.id)).toEqual(["C"]);
  });
  it("carries n_routes for reach-dot sizing, defaulting to 0", () => {
    const fc = destinationsGeoJSON(shown(reach, 3, Infinity), stationsById);
    for (const f of fc.features) expect(f.properties.n_routes).toBe(0);
  });
  it("max-minutes filter applies", () => {
    const fc = destinationsGeoJSON(shown(reach, 3, 130), stationsById);
    expect(fc.features.map((f) => f.properties.id)).toEqual(["C"]);
  });
  it("lines pass through via and transfer stations", () => {
    const fc = linesGeoJSON(reach, stationsById, 3, Infinity, null);
    const d = fc.features.find((f) => f.properties.id === "D")!;
    const lons = (d.geometry.coordinates as [number, number][]).map(([lon]) => lon);
    expect(lons[0]).toBe(8);                       // origin A preserved
    expect(lons[lons.length - 1]).toBe(11);        // dest D preserved
    expect(Math.max(...lons)).toBe(11);            // monotone-ish through B(9), C(10)
  });
});

describe("linesGeoJSON per-leg splitting", () => {
  // Barcelona(A) -> Paris(B) -> Sens(C), where leg 2 doubles back near A: whole-line
  // smoothing used to round the Paris corner into a U-curve whose apex landed ~100km
  // short of Paris, over empty countryside near Auxerre (user report 2026-07-09).
  // Handling each leg separately keeps B a sharp vertex the line visibly passes through.
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
    const fc = linesGeoJSON(hairpinReach, hairpinStations, 3, Infinity, null);
    const feature = fc.features.find((f) => f.properties.id === "C")!;
    const coords = feature.geometry.coordinates as [number, number][];
    const b = hairpinStations.get("B")!;
    const a = hairpinStations.get("A")!;
    const c = hairpinStations.get("C")!;
    expect(coords).toContainEqual([b.lon, b.lat]);
    expect(coords[0]).toEqual([a.lon, a.lat]);
    expect(coords[coords.length - 1]).toEqual([c.lon, c.lat]);
  });

  it("keeps every served stop as an exact vertex — no corner cutting (backlog X)", () => {
    // Smoothing used to round the corner at via stop B differently per destination,
    // splaying identical trunks into a fan (Nijmegen report 2026-07-13).
    const fc = linesGeoJSON(reach, stationsById, 1, Infinity, null);
    const feature = fc.features.find((f) => f.properties.id === "C")!;
    const a = stationsById.get("A")!;
    const b = stationsById.get("B")!;
    const c = stationsById.get("C")!;
    expect(feature.geometry.coordinates).toEqual([
      [a.lon, a.lat], [b.lon, b.lat], [c.lon, c.lat],
    ]);
  });

  it("journeys sharing a trunk produce identical trunk coordinates (backlog X)", () => {
    const splayReach: ReachFile = {
      origin: "A", computed_at: "", sample_date: "2026-07-14",
      destinations: [
        { id: "B", direct_per_day: 4, journeys: [
          { trains: 1, duration_min: 20, legs: [
            { train: "IC 1", dep: "08:00", arr: "08:20", from: "A", to: "B", via: [] } ] } ] },
        { id: "D", direct_per_day: 4, journeys: [
          { trains: 1, duration_min: 60, legs: [
            { train: "IC 1", dep: "08:00", arr: "09:00", from: "A", to: "D", via: ["B", "C"] } ] } ] },
      ],
    };
    const fc = linesGeoJSON(splayReach, stationsById, 3, Infinity, null);
    const toB = fc.features.find((f) => f.properties.id === "B")!.geometry.coordinates;
    const toD = fc.features.find((f) => f.properties.id === "D")!.geometry.coordinates;
    expect(toD.slice(0, toB.length)).toEqual(toB); // same trunk, point for point
  });
});

describe("segmentsGeoJSON", () => {
  it("draws each physical stop-to-stop segment exactly once (backlog X)", () => {
    // reach has A→C via B (120 min) and A→C via B then C→D (240 min): the shared
    // A–B and B–C hops must appear once, tagged with the fastest/most-direct user.
    const fc = segmentsGeoJSON(shown(reach, 3, Infinity), stationsById, null);
    expect(fc.features.map((f) => f.properties.id).sort()).toEqual(["A|B", "B|C", "C|D"]);
    const ab = fc.features.find((f) => f.properties.id === "A|B")!;
    expect(ab.properties.bucket).toBe(timeBucket(120)); // fastest journey through it
    expect(ab.properties.trains).toBe(1);               // most direct journey through it
    const cd = fc.features.find((f) => f.properties.id === "C|D")!;
    expect(cd.properties.bucket).toBe(timeBucket(240));
    expect(cd.properties.trains).toBe(2);
  });

  it("respects the train budget and max-minutes filters like linesGeoJSON", () => {
    const fc = segmentsGeoJSON(shown(reach, 1, Infinity), stationsById, null);
    expect(fc.features.map((f) => f.properties.id).sort()).toEqual(["A|B", "B|C"]);
    expect(segmentsGeoJSON(shown(reach, 3, 60), stationsById, null).features).toEqual([]);
  });
});

describe("shown", () => {
  it("matches the filter linesGeoJSON/destinationsGeoJSON used to apply internally", () => {
    expect(shown(reach, 1, Infinity).map((x) => x.d.id)).toEqual(["C"]);
    expect(shown(reach, 3, Infinity).map((x) => x.d.id)).toEqual(["C", "D"]);
    expect(shown(reach, 3, 60)).toEqual([]);
  });
});

describe("selectedLineGeoJSON (backlog AU)", () => {
  it("is empty when nothing is selected or reach is missing", () => {
    expect(selectedLineGeoJSON(reach, null, stationsById, 3, Infinity, null).features).toEqual([]);
    expect(selectedLineGeoJSON(null, "C", stationsById, 3, Infinity, null).features).toEqual([]);
  });

  it("is empty for an unknown destination id", () => {
    expect(selectedLineGeoJSON(reach, "ZZZ", stationsById, 3, Infinity, null).features).toEqual([]);
  });

  it("is empty when the selected destination is filtered out (train budget / minutes)", () => {
    // D needs 2 trains / 240 min; both filters below exclude it.
    expect(selectedLineGeoJSON(reach, "D", stationsById, 1, Infinity, null).features).toEqual([]);
    expect(selectedLineGeoJSON(reach, "D", stationsById, 3, 60, null).features).toEqual([]);
  });

  for (const id of ["C", "D"]) {
    it(`equals the old linesGeoJSON's feature for id=${id} (identity, backlog AU)`, () => {
      const old = linesGeoJSON(reach, stationsById, 3, Infinity, null)
        .features.find((f) => f.properties.id === id)!;
      const next = selectedLineGeoJSON(reach, id, stationsById, 3, Infinity, null).features;
      expect(next).toHaveLength(1);
      expect(next[0]).toEqual(old);
    });
  }

  it("equals the old linesGeoJSON output with rail-path geometry threaded through", () => {
    const railPaths = buildRailPathLookup({ "A|B": [[8, 50], [8.5, 50.2], [9, 50]] });
    const old = linesGeoJSON(reach, stationsById, 3, Infinity, railPaths)
      .features.find((f) => f.properties.id === "D")!;
    const next = selectedLineGeoJSON(reach, "D", stationsById, 3, Infinity, railPaths).features[0];
    expect(next).toEqual(old);
  });
});

describe("journeyLegPaths", () => {
  const stations = new Map([
    ["a", { id: "a", name: "A", lat: 0, lon: 0, country: "DE", has_reach: true }],
    ["b", { id: "b", name: "B", lat: 0, lon: 1, country: "DE", has_reach: true }],
    ["c", { id: "c", name: "C", lat: 1, lon: 1, country: "DE", has_reach: true }],
  ]);
  const journey = {
    trains: 2, duration_min: 100,
    legs: [
      { train: "ICE 1", dep: "08:00", arr: "09:00", from: "a", to: "b", via: [] },
      { train: "ICE 2", dep: "09:10", arr: "10:00", from: "b", to: "c", via: [] },
    ],
  };

  it("is exactly the geometry linesGeoJSON renders", () => {
    const reachData = {
      origin: "a", computed_at: "", sample_date: "",
      destinations: [{ id: "c", direct_per_day: 0, journeys: [journey] }],
    };
    const line = linesGeoJSON(reachData, stations, 3, 1440, null).features[0];
    const paths = journeyLegPaths(journey, stations, null);
    const flattened = paths.flatMap((c, i) => (i === 0 ? c : c.slice(1)));
    expect(line.geometry.coordinates).toEqual(flattened);
  });
});

const mkStation = (id: string, lon: number, lat: number): [string, Station] =>
  [id, { id, name: id, lon, lat, country: "XX", has_reach: true }];
const railStationsById = new Map<string, Station>([
  mkStation("a", 0, 0), mkStation("b", 1, 0), mkStation("c", 2, 0),
]);
const railLeg = (from: string, to: string, via: string[]): Leg =>
  ({ train: "T", dep: "", arr: "", from, to, via });

describe("legSegments with rail paths", () => {
  const railPaths: RailPathLookup = buildRailPathLookup({
    "a|b": [[0, 0], [0.5, 0.4], [1, 0]],
  });

  it("uses lookup geometry for a hop when present", () => {
    expect(legSegments(railLeg("a", "b", []), railStationsById, railPaths)[0].coords)
      .toEqual([[0, 0], [0.5, 0.4], [1, 0]]);
  });

  it("reverses geometry when the hop travels against key order", () => {
    expect(legSegments(railLeg("b", "a", []), railStationsById, railPaths)[0].coords)
      .toEqual([[1, 0], [0.5, 0.4], [0, 0]]);
    // Original forward entry must not be mutated by the reversal.
    expect(railPaths.get("a|b")!.fwd[0]).toEqual([0, 0]);
  });

  it("falls back to a straight line for hops without geometry", () => {
    expect(legSegments(railLeg("b", "c", []), railStationsById, railPaths)[0].coords)
      .toEqual([[1, 0], [2, 0]]);
  });

  it("splits a via-leg into per-hop segments, each with its own lookup", () => {
    const segments = legSegments(railLeg("a", "c", ["b"]), railStationsById, railPaths);
    expect(segments.map((s) => s.key)).toEqual(["a|b", "b|c"]);
    expect(segments[0].coords).toEqual([[0, 0], [0.5, 0.4], [1, 0]]);
    expect(segments[1].coords).toEqual([[1, 0], [2, 0]]);
  });

  it("journeyLegPaths threads geometry and keeps stops as exact vertices", () => {
    const journey = { trains: 1, duration_min: 60, legs: [railLeg("a", "c", ["b"])] };
    expect(journeyLegPaths(journey, railStationsById, railPaths))
      .toEqual([[[0, 0], [0.5, 0.4], [1, 0], [2, 0]]]);
  });
});

describe("initialMaxTrains", () => {
  it("resolves from trains URL param when valid", () => {
    expect(initialMaxTrains("?trains=1", "localhost")).toBe(1);
    expect(initialMaxTrains("?trains=2", "localhost")).toBe(2);
    expect(initialMaxTrains("?trains=3", "localhost")).toBe(3);
  });

  it("ignores invalid trains URL params and falls back to default", () => {
    expect(initialMaxTrains("?trains=4", "localhost")).toBe(1);
    expect(initialMaxTrains("?trains=x", "localhost")).toBe(1);
    expect(initialMaxTrains("?trains=", "localhost")).toBe(1);
    expect(initialMaxTrains("", "localhost")).toBe(1);
  });

  it("defaults to 1 for nonstop domains when no URL param is present", () => {
    expect(initialMaxTrains("", "nonstopeurope.eu")).toBe(1);
    expect(initialMaxTrains("", "www.nonstopeurope.eu")).toBe(1);
  });

  it("prioritizes URL param over nonstop domains", () => {
    expect(initialMaxTrains("?trains=2", "nonstopeurope.eu")).toBe(2);
    expect(initialMaxTrains("?trains=3", "www.nonstopeurope.eu")).toBe(3);
  });

  it("defaults to onestop (2 trains) on onestopeurope domains", () => {
    expect(initialMaxTrains("", "onestopeurope.eu")).toBe(2);
    expect(initialMaxTrains("", "www.onestopeurope.eu")).toBe(2);
    expect(initialMaxTrains("?trains=1", "onestopeurope.eu")).toBe(1);
  });

  it("keeps default for other hostnames", () => {
    expect(initialMaxTrains("", "google.com")).toBe(1);
  });
});

