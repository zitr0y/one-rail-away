import type { Destination, Journey, ReachFile, Station } from "./types";

export type MaxTrains = 1 | 2 | 3;

export function bestJourney(d: Destination, maxTrains: MaxTrains): Journey | null {
  const eligible = d.journeys.filter((j) => j.trains <= maxTrains);
  return eligible.length
    ? eligible.reduce((a, b) => (b.duration_min < a.duration_min ? b : a))
    : null;
}

export function timeBucket(min: number): 0 | 1 | 2 | 3 {
  if (min < 180) return 0;
  if (min < 360) return 1;
  if (min < 600) return 2;
  return 3;
}

export function chaikin(coords: [number, number][], iterations: number): [number, number][] {
  let pts = coords;
  for (let it = 0; it < iterations; it++) {
    if (pts.length < 3) break;
    const next: [number, number][] = [pts[0]];
    for (let i = 0; i < pts.length - 1; i++) {
      const [ax, ay] = pts[i];
      const [bx, by] = pts[i + 1];
      next.push([ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25]);
      next.push([ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75]);
    }
    next.push(pts[pts.length - 1]);
    pts = next;
  }
  return pts;
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
      },
    });
  }
  return { type: "FeatureCollection", features };
}

export function linesGeoJSON(
  reach: ReachFile, stationsById: Map<string, Station>, maxTrains: MaxTrains, maxMinutes: number,
): FC<LineString> {
  const features: Feature<LineString>[] = [];
  for (const { d, j } of shown(reach, maxTrains, maxMinutes)) {
    const ids = [j.legs[0].from, ...j.legs.flatMap((leg) => [...leg.via, leg.to])];
    const coords = ids
      .map((id) => stationsById.get(id))
      .filter((s): s is Station => s !== undefined)
      .map((s): [number, number] => [s.lon, s.lat]);
    if (coords.length < 2) continue;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: chaikin(coords, 2) },
      properties: { id: d.id, bucket: timeBucket(j.duration_min), trains: j.trains },
    });
  }
  return { type: "FeatureCollection", features };
}
