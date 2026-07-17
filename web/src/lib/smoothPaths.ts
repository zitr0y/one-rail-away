/** Client-side smoothed "subway map style" curves for reach-line hops
 *  (backlog I — replaces the OSM-routed `ose paths` geometry, 2026-07-17).
 *
 *  Every train hop in the origin's FULL reach file gets a gentle cubic-Bézier
 *  curve through the real station positions. By construction: stations are
 *  EXACT curve endpoints (trunk-dedup + rider invariant, backlog X); a hop
 *  shared by many journeys has exactly one geometry (trunks stay merged); a
 *  line passing through a station enters and leaves along one shared tangent
 *  (no kink at served stops); branches leave a trunk along the shared tangent,
 *  then bend away.
 *
 *  Pure functions — no map or React dependency. Never throws: malformed input
 *  degrades to an empty lookup, and hopCoords (geojson.ts) falls back to
 *  straight lines for anything missing. */
import { isTrainLeg, segmentKey, type HopGeometryLookup } from "./geojson";
import type { ReachFile, Station } from "./types";

/** Tunable curvature factor for smoothed hop control points.
 *  0.25 read as barely-curved; 0.35 chosen with the user 2026-07-17.
 *  MAX_CONTROL_FRACTION (0.4) is the self-intersection ceiling. */
export const CURVINESS = 0.35;

/** Planar direction/position vector: [x (east), y (north)]. */
export type Vec = [number, number];

/** One physical hop of the graph. `a < b` (segmentKey order). */
export interface Hop { a: string; b: string; weight: number }

/** Every train hop in the reach file, keyed by segmentKey(a, b), weighted by
 *  the number of journey traversals. Transfer legs contribute nothing; hops
 *  between identical consecutive stop ids are dropped. Defensive against
 *  malformed input: anything unexpected yields fewer hops, never a throw. */
export function expandHops(reach: ReachFile): Map<string, Hop> {
  const hops = new Map<string, Hop>();
  const destinations = Array.isArray(reach?.destinations) ? reach.destinations : [];
  for (const d of destinations) {
    const journeys = Array.isArray(d?.journeys) ? d.journeys : [];
    for (const j of journeys) {
      const legs = Array.isArray(j?.legs) ? j.legs : [];
      for (const leg of legs) {
        if (!leg || typeof leg !== "object" || !isTrainLeg(leg)) continue;
        if (typeof leg.from !== "string" || typeof leg.to !== "string") continue;
        const via = Array.isArray(leg.via) ? leg.via.filter((id): id is string => typeof id === "string") : [];
        const stops = [leg.from, ...via, leg.to];
        for (let i = 0; i < stops.length - 1; i++) {
          const s = stops[i];
          const t = stops[i + 1];
          if (s === t) continue; // zero-length hop
          const key = segmentKey(s, t);
          const hop = hops.get(key);
          if (hop) hop.weight += 1;
          else hops.set(key, { a: s < t ? s : t, b: s < t ? t : s, weight: 1 });
        }
      }
    }
  }
  return hops;
}

/** Unit vector from `a` toward `b` in a locally angle-true plane: lon scaled
 *  by cos(mid latitude) so directions are true angles, not lon/lat-squished.
 *  Zero vector when the stations coincide. */
function direction(a: Station, b: Station): Vec {
  const midLat = ((a.lat + b.lat) / 2) * (Math.PI / 180);
  const dx = (b.lon - a.lon) * Math.cos(midLat);
  const dy = b.lat - a.lat;
  const len = Math.hypot(dx, dy);
  return len === 0 ? [0, 0] : [dx / len, dy / len];
}

function push<K, V>(map: Map<K, V[]>, key: K, value: V): void {
  const list = map.get(key);
  if (list) list.push(value);
  else map.set(key, [value]);
}

/** All incident directions point AWAY from the station. A pair that passes
 *  straight through has opposing directions (dot ≈ −1), so alignment
 *  (1 − dot) / 2 is 1 for straight-through and 0 for a doubled-back pair.
 *  The winning pair's tangent is its bisector with one side flipped so the
 *  two oppose: normalize(u − v). */
function dominantTangent(list: { dir: Vec; weight: number }[]): Vec {
  if (list.length === 1) return list[0].dir;
  let best: Vec = list[0].dir;
  let bestScore = -Infinity;
  for (let i = 0; i < list.length; i++) {
    for (let j = i + 1; j < list.length; j++) {
      const u = list[i].dir;
      const v = list[j].dir;
      const alignment = (1 - (u[0] * v[0] + u[1] * v[1])) / 2;
      const score = (list[i].weight + list[j].weight) * alignment;
      if (score > bestScore) {
        bestScore = score;
        const t: Vec = [u[0] - v[0], u[1] - v[1]];
        const len = Math.hypot(t[0], t[1]);
        best = len === 0 ? u : [t[0] / len, t[1] / len];
      }
    }
  }
  return best;
}

/** Exactly ONE tangent per station: degree 1 → its hop's direction; degree
 *  ≥ 2 → the dominant through-direction (combined weight × straightness
 *  alignment). Hops with a station missing from `byId` are ignored (they fall
 *  back to straight lines at render). Iteration runs over SORTED hop keys so
 *  the result is independent of journey order in the reach file. */
export function stationTangents(
  hops: Map<string, Hop>, byId: Map<string, Station>,
): Map<string, Vec> {
  const incident = new Map<string, { dir: Vec; weight: number }[]>();
  for (const key of [...hops.keys()].sort()) {
    const hop = hops.get(key)!;
    const a = byId.get(hop.a);
    const b = byId.get(hop.b);
    if (!a || !b) continue;
    const dirAB = direction(a, b);
    if (dirAB[0] === 0 && dirAB[1] === 0) continue; // co-located stations
    push(incident, hop.a, { dir: dirAB, weight: hop.weight });
    push(incident, hop.b, { dir: [-dirAB[0], -dirAB[1]], weight: hop.weight });
  }
  const tangents = new Map<string, Vec>();
  for (const [id, list] of incident) tangents.set(id, dominantTangent(list));
  return tangents;
}

/** Control points never exceed this fraction of the hop length (self-
 *  intersection guard if CURVINESS is ever tuned up)... */
const MAX_CONTROL_FRACTION = 0.4;
/** ...nor this absolute distance, so short hops in dense areas don't
 *  overshoot into neighbouring stations. */
const MAX_CONTROL_KM = 30;

const KM_PER_DEG = 111.32; // per degree of latitude; lon scaled by cos(lat)

// Sampling: points per curve scale with hop length between these bounds.
const MIN_POINTS = 8;
const MAX_POINTS = 40;
const KM_PER_POINT = 12;

function hopLengthKm(a: Station, b: Station): number {
  const midLat = ((a.lat + b.lat) / 2) * (Math.PI / 180);
  const dx = (b.lon - a.lon) * Math.cos(midLat) * KM_PER_DEG;
  const dy = (b.lat - a.lat) * KM_PER_DEG;
  return Math.hypot(dx, dy);
}

/** Flip `t` if needed so it points along `dir` (non-negative dot). */
function flipAlong(t: Vec, dir: Vec): Vec {
  return t[0] * dir[0] + t[1] * dir[1] >= 0 ? t : [-t[0], -t[1]];
}

/** The point `km` kilometres from station `s` along planar unit vector `v`,
 *  back in [lon, lat] degrees (lon un-scaled by cos of the station's lat). */
function offsetKm(s: Station, v: Vec, km: number): Vec {
  const cosLat = Math.cos(s.lat * (Math.PI / 180));
  return [s.lon + (km * v[0]) / (KM_PER_DEG * cosLat), s.lat + (km * v[1]) / KM_PER_DEG];
}

function cubic(p0: Vec, p1: Vec, p2: Vec, p3: Vec, t: number): [number, number] {
  const u = 1 - t;
  const c0 = u * u * u;
  const c1 = 3 * u * u * t;
  const c2 = 3 * u * t * t;
  const c3 = t * t * t;
  return [
    c0 * p0[0] + c1 * p1[0] + c2 * p2[0] + c3 * p3[0],
    c0 * p0[1] + c1 * p1[1] + c2 * p2[1] + c3 * p3[1],
  ];
}

function dedupeConsecutive(coords: [number, number][]): [number, number][] {
  const out: [number, number][] = [];
  for (const c of coords) {
    const last = out[out.length - 1];
    if (last && last[0] === c[0] && last[1] === c[1]) continue;
    out.push(c);
  }
  return out;
}

/** One hop's cubic Bézier, oriented a→b, sampled to a polyline. First/last
 *  vertices are EXACTLY the station coordinates (assigned, not computed — no
 *  float drift). `ta`/`tb` are the stations' tangents, sign-corrected here to
 *  point along the a→b travel direction. */
function hopCurve(a: Station, b: Station, ta: Vec, tb: Vec): [number, number][] {
  const lengthKm = hopLengthKm(a, b);
  if (lengthKm === 0) return dedupeConsecutive([[a.lon, a.lat], [b.lon, b.lat]]);
  const dirAB = direction(a, b);
  const sa = flipAlong(ta, dirAB);
  const sb = flipAlong(tb, dirAB);
  const d = Math.min(CURVINESS * lengthKm, MAX_CONTROL_FRACTION * lengthKm, MAX_CONTROL_KM);
  const p0: Vec = [a.lon, a.lat];
  const p3: Vec = [b.lon, b.lat];
  const p1 = offsetKm(a, sa, d);
  const p2 = offsetKm(b, sb, -d);
  const points = Math.min(MAX_POINTS, Math.max(MIN_POINTS, Math.round(lengthKm / KM_PER_POINT)));
  const out: [number, number][] = [];
  for (let i = 0; i < points; i++) out.push(cubic(p0, p1, p2, p3, i / (points - 1)));
  out[0] = [a.lon, a.lat];
  out[out.length - 1] = [b.lon, b.lat];
  return dedupeConsecutive(out);
}

/** The smoothed lookup for a reach file: one HopGeometry per train hop, keyed
 *  by segmentKey, `fwd` oriented idA→idB (idA < idB). MUST be built from the
 *  FULL reach file — filters (1/2/3 trains, time slider) hide lines but never
 *  reshape them. Never throws: malformed input yields an empty lookup and the
 *  render side falls back to straight lines. */
export function buildSmoothedLookup(
  reach: ReachFile, byId: Map<string, Station>,
): HopGeometryLookup {
  try {
    const hops = expandHops(reach);
    const tangents = stationTangents(hops, byId);
    const lookup: HopGeometryLookup = new Map();
    for (const key of [...hops.keys()].sort()) {
      const hop = hops.get(key)!;
      const a = byId.get(hop.a);
      const b = byId.get(hop.b);
      if (!a || !b) continue; // stale reach vs stations.json → straight fallback
      const dirAB = direction(a, b);
      const fwd = hopCurve(a, b, tangents.get(hop.a) ?? dirAB, tangents.get(hop.b) ?? dirAB);
      if (fwd.length < 2) continue; // co-located stations degenerate away
      lookup.set(key, { fwd, rev: [...fwd].reverse() });
    }
    return lookup;
  } catch {
    return new Map();
  }
}

/** Memoized per reach-file identity (and stations identity) so filter and
 *  selection churn never recomputes — a full reach file is ~4k hops worst
 *  case, target <10 ms, but once is still better than every render. */
const memo = new WeakMap<ReachFile, { byId: Map<string, Station>; lookup: HopGeometryLookup }>();

export function smoothedLookupFor(
  reach: ReachFile, byId: Map<string, Station>,
): HopGeometryLookup {
  const hit = memo.get(reach);
  if (hit && hit.byId === byId) return hit.lookup;
  const lookup = buildSmoothedLookup(reach, byId);
  memo.set(reach, { byId, lookup });
  return lookup;
}
