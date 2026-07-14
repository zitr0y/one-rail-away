import type { Destination, Journey, Leg, ReachFile, Station } from "./types";

export type MaxTrains = 1 | 2 | 3;

export function bestJourney(d: Destination, maxTrains: MaxTrains): Journey | null {
  const eligible = d.journeys.filter((j) => j.trains <= maxTrains);
  return eligible.length
    ? eligible.reduce((a, b) => (b.duration_min < a.duration_min ? b : a))
    : null;
}

/** Old reach files have no evidence metadata, so retain their established solid style. */
export function frequencyClass(d: Destination): "frequent" | "infrequent" {
  return d.frequency?.seasonal || d.frequency?.availability === "seasonal_or_limited"
    ? "infrequent" : "frequent";
}

export function timeBucket(min: number): 0 | 1 | 2 | 3 {
  if (min < 180) return 0;
  if (min < 360) return 1;
  if (min < 600) return 2;
  return 3;
}

/** Coordinates of the stations where a selected journey changes legs. */
export function transferPoints(
  journey: Journey, stationsById: Map<string, Station>,
): [number, number][] {
  return journey.legs.slice(0, -1).flatMap((leg) => {
    const station = stationsById.get(leg.to);
    return station ? [[station.lon, station.lat] as [number, number]] : [];
  });
}

type FC<G> = { type: "FeatureCollection"; features: Feature<G>[] };
type Feature<G> = { type: "Feature"; geometry: G; properties: Record<string, unknown> & { id: string } };
type Point = { type: "Point"; coordinates: [number, number] };
type LineString = { type: "LineString"; coordinates: [number, number][] };

function shown(reach: ReachFile, maxTrains: MaxTrains, maxMinutes: number) {
  return reach.destinations
    .map((d) => ({ d, j: bestJourney(d, maxTrains) }))
    .filter((x): x is { d: Destination; j: Journey } => x.j !== null && x.j.duration_min <= maxMinutes);
}

export function destinationsGeoJSON(
  reach: ReachFile, stationsById: Map<string, Station>, maxTrains: MaxTrains, maxMinutes: number,
): FC<Point> {
  const features: Feature<Point>[] = [];
  for (const { d, j } of shown(reach, maxTrains, maxMinutes)) {
    const s = stationsById.get(d.id);
    if (!s) continue;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [s.lon, s.lat] },
      properties: {
        id: d.id, name: s.name, duration_min: j.duration_min, trains: j.trains,
        bucket: timeBucket(j.duration_min), direct_per_day: d.direct_per_day,
        frequency_class: frequencyClass(d),
        n_routes: s.n_routes ?? 0,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

/** One physical piece of a leg: a stop-to-stop hop. `key` is
 *  direction-normalized so the same track traversed by many journeys
 *  collapses to one drawn segment. */
export interface LegSegment { key: string; coords: [number, number][] }

function segmentKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

/** Precomputed real-track geometry per physical hop, keyed by segmentKey and
 *  stored oriented idA→idB (idA < idB). Built by `ose paths` (backlog I). */
export type RailPathLookup = Map<string, [number, number][]>;

function hopCoords(
  a: { id: string; station: Station }, b: { id: string; station: Station },
  railPaths: RailPathLookup | null,
): [number, number][] {
  const geometry = railPaths?.get(segmentKey(a.id, b.id));
  if (geometry && geometry.length >= 2) {
    return a.id < b.id ? geometry : [...geometry].reverse();
  }
  return [[a.station.lon, a.station.lat], [b.station.lon, b.station.lat]];
}

export function legSegments(
  leg: Leg, stationsById: Map<string, Station>, railPaths: RailPathLookup | null,
): LegSegment[] {
  const stops = [leg.from, ...leg.via, leg.to]
    .map((id) => ({ id, station: stationsById.get(id) }))
    .filter((x): x is { id: string; station: Station } => x.station !== undefined);
  if (stops.length < 2) return [];
  const segments: LegSegment[] = [];
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i];
    const b = stops[i + 1];
    segments.push({ key: segmentKey(a.id, b.id), coords: hopCoords(a, b, railPaths) });
  }
  return segments;
}

/** Per-leg coordinate paths for a journey — shared by linesGeoJSON and the
 *  mascot rider (ride.ts) so the two can never drift. Served stops are EXACT
 *  vertices: real-track geometry must never cut a stop's corner, otherwise
 *  journeys sharing a trunk round it differently per destination and the
 *  overlapping trunks splay into a fan (backlog X, user report 2026-07-13).
 *  Paths stay per leg so transfer corners stay sharp (user report 2026-07-09). */
export function journeyLegPaths(
  j: Journey, stationsById: Map<string, Station>, railPaths: RailPathLookup | null,
): [number, number][][] {
  return j.legs
    .map((leg) => legSegments(leg, stationsById, railPaths))
    .filter((segments) => segments.length > 0)
    .map((segments) => segments.flatMap((s, i) => (i === 0 ? s.coords : s.coords.slice(1))));
}

/** Deduplicated physical segments across all shown journeys — feeds the base
 *  reach-lines layer (backlog X). Each stop-to-stop hop is drawn exactly once,
 *  so a multi-stop train reads as one trunk threading its stops instead of a
 *  per-destination fan. A shared segment takes the bucket of the fastest
 *  journey through it and the width class (trains) of the most direct one. */
export function segmentsGeoJSON(
  reach: ReachFile, stationsById: Map<string, Station>, maxTrains: MaxTrains, maxMinutes: number,
  railPaths: RailPathLookup | null,
): FC<LineString> {
  const best = new Map<string, {
    coords: [number, number][]; duration_min: number; trains: number; frequency_class: string;
  }>();
  for (const { d, j } of shown(reach, maxTrains, maxMinutes)) {
    for (const leg of j.legs) {
      for (const segment of legSegments(leg, stationsById, railPaths)) {
        const prev = best.get(segment.key);
        if (!prev) {
          best.set(segment.key, {
            coords: segment.coords, duration_min: j.duration_min, trains: j.trains,
            frequency_class: frequencyClass(d),
          });
        } else {
          prev.duration_min = Math.min(prev.duration_min, j.duration_min);
          prev.trains = Math.min(prev.trains, j.trains);
          // A shared trunk stays visually dominant when any frequent route uses it.
          if (frequencyClass(d) === "frequent") prev.frequency_class = "frequent";
        }
      }
    }
  }
  const features: Feature<LineString>[] = [];
  for (const [key, s] of best) {
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: s.coords },
      properties: {
        id: key, bucket: timeBucket(s.duration_min), trains: s.trains,
        frequency_class: s.frequency_class,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

/** One full LineString per destination — feeds only the selected-journey
 *  highlight layer; the base layer draws segmentsGeoJSON. */
export function linesGeoJSON(
  reach: ReachFile, stationsById: Map<string, Station>, maxTrains: MaxTrains, maxMinutes: number,
  railPaths: RailPathLookup | null,
): FC<LineString> {
  const features: Feature<LineString>[] = [];
  for (const { d, j } of shown(reach, maxTrains, maxMinutes)) {
    const coords = journeyLegPaths(j, stationsById, railPaths)
      .flatMap((c, i) => (i === 0 ? c : c.slice(1)));
    if (coords.length < 2) continue;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: coords },
      properties: {
        id: d.id, bucket: timeBucket(j.duration_min), trains: j.trains,
        frequency_class: frequencyClass(d),
      },
    });
  }
  return { type: "FeatureCollection", features };
}
