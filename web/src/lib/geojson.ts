import type { Destination, Journey, JourneyLeg, Leg, ReachFile, Station } from "./types";

export type MaxTrains = 1 | 2 | 3;

export function isTrainLeg(leg: JourneyLeg): leg is Leg {
  return leg.type !== "transfer";
}

export function bestJourney(d: Destination, maxTrains: MaxTrains): Journey | null {
  const eligible = d.journeys.filter((j) => j.trains <= maxTrains);
  return eligible.length
    ? eligible.reduce((a, b) => (b.duration_min < a.duration_min ? b : a))
    : null;
}

/** Old reach files have no evidence metadata (or carry a retired availability
 *  value), so anything but the honest "limited" signal renders solid. */
export function frequencyClass(d: Destination): "frequent" | "infrequent" {
  return d.frequency?.availability === "limited" ? "infrequent" : "frequent";
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
  return journey.legs.filter(isTrainLeg).slice(0, -1).flatMap((leg) => {
    const station = stationsById.get(leg.to);
    return station ? [[station.lon, station.lat] as [number, number]] : [];
  });
}

type FC<G> = { type: "FeatureCollection"; features: Feature<G>[] };
type Feature<G> = { type: "Feature"; geometry: G; properties: Record<string, unknown> & { id: string } };
type Point = { type: "Point"; coordinates: [number, number] };
type LineString = { type: "LineString"; coordinates: [number, number][] };

export interface ShownEntry { d: Destination; j: Journey }

/** Which destinations are within the current train/time filter — computed
 *  once per update (backlog AU) and threaded into the builders below instead
 *  of each one recomputing it from scratch. */
export function shown(reach: ReachFile, maxTrains: MaxTrains, maxMinutes: number): ShownEntry[] {
  return reach.destinations
    .map((d) => ({ d, j: bestJourney(d, maxTrains) }))
    .filter((x): x is ShownEntry => x.j !== null && x.j.duration_min <= maxMinutes);
}

export function destinationsGeoJSON(
  shownList: ShownEntry[], stationsById: Map<string, Station>,
): FC<Point> {
  const features: Feature<Point>[] = [];
  for (const { d, j } of shownList) {
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

/** Direction-normalized hop key ("idA|idB", ids sorted) — shared with
 *  smoothPaths.ts, which builds its lookup under the same keys. */
export function segmentKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

/** Both traversal orientations of one physical hop's geometry: `fwd` runs
 *  idA→idB (idA < idB), `rev` is the same points reversed. Precomputed once
 *  (backlog AU) so per-hop lookups never allocate a `.reverse()` copy. */
export interface HopGeometry { fwd: [number, number][]; rev: [number, number][] }

/** Precomputed smoothed geometry per physical hop, keyed by segmentKey.
 *  Built client-side by smoothPaths.ts (backlog I). */
export type HopGeometryLookup = Map<string, HopGeometry>;

function hopCoords(
  a: { id: string; station: Station }, b: { id: string; station: Station },
  hopGeometry: HopGeometryLookup | null,
): [number, number][] {
  const geometry = hopGeometry?.get(segmentKey(a.id, b.id));
  if (geometry && geometry.fwd.length >= 2) {
    return a.id < b.id ? geometry.fwd : geometry.rev;
  }
  return [[a.station.lon, a.station.lat], [b.station.lon, b.station.lat]];
}

export function legSegments(
  leg: Leg, stationsById: Map<string, Station>, hopGeometry: HopGeometryLookup | null,
): LegSegment[] {
  const stops = [leg.from, ...leg.via, leg.to]
    .map((id) => ({ id, station: stationsById.get(id) }))
    .filter((x): x is { id: string; station: Station } => x.station !== undefined);
  if (stops.length < 2) return [];
  const segments: LegSegment[] = [];
  for (let i = 0; i < stops.length - 1; i++) {
    const a = stops[i];
    const b = stops[i + 1];
    segments.push({ key: segmentKey(a.id, b.id), coords: hopCoords(a, b, hopGeometry) });
  }
  return segments;
}

/** Per-leg coordinate paths for a journey — shared by linesGeoJSON and the
 *  mascot rider (ride.ts) so the two can never drift. Served stops are EXACT
 *  vertices: hop geometry must never cut a stop's corner, otherwise
 *  journeys sharing a trunk round it differently per destination and the
 *  overlapping trunks splay into a fan (backlog X, user report 2026-07-13).
 *  Paths stay per leg so transfer corners stay sharp (user report 2026-07-09). */
export function journeyLegPaths(
  j: Journey, stationsById: Map<string, Station>, hopGeometry: HopGeometryLookup | null,
): [number, number][][] {
  return j.legs
    .filter(isTrainLeg)
    .map((leg) => legSegments(leg, stationsById, hopGeometry))
    .filter((segments) => segments.length > 0)
    .map((segments) => segments.flatMap((s, i) => (i === 0 ? s.coords : s.coords.slice(1))));
}

/** Deduplicated physical segments across all shown journeys — feeds the base
 *  reach-lines layer (backlog X). Each stop-to-stop hop is drawn exactly once,
 *  so a multi-stop train reads as one trunk threading its stops instead of a
 *  per-destination fan. A shared segment takes the bucket of the fastest
 *  journey through it and the width class (trains) of the most direct one. */
export function segmentsGeoJSON(
  shownList: ShownEntry[], stationsById: Map<string, Station>,
  hopGeometry: HopGeometryLookup | null,
): FC<LineString> {
  const best = new Map<string, {
    coords: [number, number][]; duration_min: number; trains: number; frequency_class: string;
  }>();
  for (const { d, j } of shownList) {
    for (const leg of j.legs) {
      if (!isTrainLeg(leg)) continue;
      for (const segment of legSegments(leg, stationsById, hopGeometry)) {
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
  hopGeometry: HopGeometryLookup | null,
): FC<LineString> {
  const features: Feature<LineString>[] = [];
  for (const { d, j } of shown(reach, maxTrains, maxMinutes)) {
    const coords = journeyLegPaths(j, stationsById, hopGeometry)
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

/** The single feature `linesGeoJSON` would have produced for `selectedDest` —
 *  the "reach-lines-selected" layer only ever draws one destination's line, so
 *  building all ~1,178 (backlog AU) to throw away everything but one is waste.
 *  Byte-for-byte the same geometry/properties as `linesGeoJSON(...).features`
 *  filtered to that id — proven by test, not just by inspection. */
export function selectedLineGeoJSON(
  reach: ReachFile | null, selectedDest: string | null, stationsById: Map<string, Station>,
  maxTrains: MaxTrains, maxMinutes: number, hopGeometry: HopGeometryLookup | null,
): FC<LineString> {
  const empty: FC<LineString> = { type: "FeatureCollection", features: [] };
  if (!reach || !selectedDest) return empty;
  const d = reach.destinations.find((x) => x.id === selectedDest);
  if (!d) return empty;
  const j = bestJourney(d, maxTrains);
  if (!j || j.duration_min > maxMinutes) return empty;
  const coords = journeyLegPaths(j, stationsById, hopGeometry)
    .flatMap((c, i) => (i === 0 ? c : c.slice(1)));
  if (coords.length < 2) return empty;
  return {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      geometry: { type: "LineString", coordinates: coords },
      properties: {
        id: d.id, bucket: timeBucket(j.duration_min), trains: j.trains,
        frequency_class: frequencyClass(d),
      },
    }],
  };
}

/** Initial 1/2/3-trains selection (backlog V): ?trains= wins, then the domain
 *  pun — nonstopeurope.eu preselects nonstop (1 train), onestopeurope.eu
 *  onestop (2 trains) — and any other host keeps the plain default. */
export function initialMaxTrains(search: string, hostname: string): MaxTrains {
  const trainsParam = new URLSearchParams(search).get("trains");
  if (trainsParam === "1" || trainsParam === "2" || trainsParam === "3") {
    return Number(trainsParam) as MaxTrains;
  }
  const host = hostname.replace(/^www\./, "");
  if (host === "nonstopeurope.eu") return 1;
  if (host === "onestopeurope.eu") return 2;
  return 1;
}
