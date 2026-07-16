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
import { isTrainLeg, segmentKey } from "./geojson";
import type { ReachFile, Station } from "./types";

/** Tunable curvature factor for smoothed hop control points. */
export const CURVINESS = 0.25;

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
