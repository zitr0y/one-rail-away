// Mascot-rider geometry & timing: pure helpers, no MapLibre/DOM.
// Spec: docs/superpowers/specs/2026-07-12-branding-phase2-design.md §Mascot rider.

/** One full origin→destination traverse, regardless of journey length. Fixed
 *  duration confirmed on the real map (user, 2026-07-12): longer journeys are
 *  usually viewed more zoomed-out, so a constant wall-clock traverse — i.e.
 *  faster per km on long trips — reads as natural rather than sluggish. */
export const TRAVERSE_MS = 7000;
/** Dwell at each transfer station — reads as "changing trains". */
export const TRANSFER_PAUSE_MS = 500;
/** Rest at the destination before the loop restarts from the origin. */
export const REST_MS = 1000;

interface MovePhase {
  kind: "move";
  startMs: number;
  endMs: number;
  path: [number, number][];
  /** Cumulative km at each path vertex; cumKm[0] = 0. */
  cumKm: number[];
  totalKm: number;
}
interface DwellPhase {
  kind: "dwell";
  startMs: number;
  endMs: number;
  at: [number, number];
  /** Bearing of the segment we arrived on, so the train doesn't snap during dwells. */
  bearingDeg: number;
}
export interface RideTimeline {
  phases: (MovePhase | DwellPhase)[];
  totalMs: number;
}
export interface RideState {
  lng: number;
  lat: number;
  bearingDeg: number;
  moving: boolean;
}

/** Smoothstep ease-in-out applied to each leg's progress: the rider accelerates
 *  away from a station and decelerates into the next, so transfer stops feel
 *  gradual, not abrupt (user calibration 2026-07-12). Fixes endpoints and the
 *  midpoint (0, 0.5, 1), so per-leg timing is unchanged. */
function easeInOut(f: number): number {
  return f * f * (3 - 2 * f);
}

/** Equirectangular distance with cos-latitude correction — plenty at journey scale. */
function segmentKm(a: [number, number], b: [number, number]): number {
  const kmPerDegLat = 111.32;
  const midLatRad = (((a[1] + b[1]) / 2) * Math.PI) / 180;
  const dx = (b[0] - a[0]) * kmPerDegLat * Math.cos(midLatRad);
  const dy = (b[1] - a[1]) * kmPerDegLat;
  return Math.hypot(dx, dy);
}

/** Compass bearing a→b: 0 = north, 90 = east, clockwise — the convention
 *  maplibregl.Marker.setRotation expects with rotationAlignment "map". */
function bearingDeg(a: [number, number], b: [number, number]): number {
  const midLatRad = (((a[1] + b[1]) / 2) * Math.PI) / 180;
  const dx = (b[0] - a[0]) * Math.cos(midLatRad);
  const dy = b[1] - a[1];
  return (Math.atan2(dx, dy) * 180) / Math.PI;
}

/** Index i such that km falls within (cumKm[i-1], cumKm[i]] — the segment to
 *  interpolate within. km must already be clamped to [0, cumKm[last]]. */
function segmentIndexAt(cumKm: number[], km: number): number {
  let i = 1;
  while (i < cumKm.length - 1 && cumKm[i] < km) i++;
  return i;
}

/** Interpolates a point at arc-length `km` along `path` (whose cumulative
 *  per-vertex distances are `cumKm`), clamped to both ends of the polyline.
 *  Single code path shared by position lookup and the heading look-ahead. */
export function positionAtKm(
  path: [number, number][],
  cumKm: number[],
  km: number,
): [number, number] {
  const totalKm = cumKm[cumKm.length - 1];
  const target = Math.min(Math.max(km, 0), totalKm);
  const i = segmentIndexAt(cumKm, target);
  const a = path[i - 1];
  const b = path[i];
  const segLen = cumKm[i] - cumKm[i - 1];
  const g = segLen === 0 ? 0 : (target - cumKm[i - 1]) / segLen;
  return [a[0] + (b[0] - a[0]) * g, a[1] + (b[1] - a[1]) * g];
}

/** Heading look-ahead window (km, each side of the current position).
 *  Geometry is now smoothly sampled Béziers (smoothPaths.ts), so per-segment
 *  bearings are already tame; the window just keeps rotation gentle across
 *  sample-point boundaries. TUNING POINT: lower it if the rider visibly
 *  "cuts corners" on tight curves. */
const BEARING_WINDOW_KM = 0.35;

export interface RideOptions {
  traverseMs?: number;
  transferPauseMs?: number;
  restMs?: number;
}

/** Builds the looping phase timeline: per-leg moves (time ∝ leg length),
 *  transfer dwells between legs, one rest dwell at the destination.
 *  Returns null when there is nothing to ride (no legs / zero length). */
export function buildRideTimeline(
  legPaths: [number, number][][],
  opts: RideOptions = {},
): RideTimeline | null {
  const traverseMs = opts.traverseMs ?? TRAVERSE_MS;
  const transferPauseMs = opts.transferPauseMs ?? TRANSFER_PAUSE_MS;
  const restMs = opts.restMs ?? REST_MS;

  const legs = legPaths
    .filter((p) => p.length >= 2)
    .map((path) => {
      const cumKm = [0];
      for (let i = 1; i < path.length; i++) {
        cumKm.push(cumKm[i - 1] + segmentKm(path[i - 1], path[i]));
      }
      return { path, cumKm, totalKm: cumKm[cumKm.length - 1] };
    });
  const grandKm = legs.reduce((sum, l) => sum + l.totalKm, 0);
  if (legs.length === 0 || grandKm === 0) return null;

  const phases: (MovePhase | DwellPhase)[] = [];
  let t = 0;
  legs.forEach((leg, i) => {
    const moveMs = traverseMs * (leg.totalKm / grandKm);
    phases.push({ kind: "move", startMs: t, endMs: t + moveMs, ...leg });
    t += moveMs;
    const end = leg.path[leg.path.length - 1];
    const arrivalBearing = bearingDeg(leg.path[leg.path.length - 2], end);
    const dwellMs = i < legs.length - 1 ? transferPauseMs : restMs;
    phases.push({
      kind: "dwell",
      startMs: t,
      endMs: t + dwellMs,
      at: end,
      bearingDeg: arrivalBearing,
    });
    t += dwellMs;
  });
  return { phases, totalMs: t };
}

/** Position + heading at wall-clock offset tMs (loops via modulo). */
export function rideStateAt(timeline: RideTimeline, tMs: number): RideState {
  const t = ((tMs % timeline.totalMs) + timeline.totalMs) % timeline.totalMs;
  const phase =
    timeline.phases.find((p) => t >= p.startMs && t < p.endMs) ??
    timeline.phases[timeline.phases.length - 1];
  if (phase.kind === "dwell") {
    return { lng: phase.at[0], lat: phase.at[1], bearingDeg: phase.bearingDeg, moving: false };
  }
  const f = easeInOut((t - phase.startMs) / (phase.endMs - phase.startMs));
  const target = f * phase.totalKm;
  const [lng, lat] = positionAtKm(phase.path, phase.cumKm, target);

  // Look-ahead heading: bearing between points BEARING_WINDOW_KM behind and
  // ahead of the current position, clamped to the leg's extent, so sub-50m
  // jitter and sideways station stubs (a few tens of metres) can't dominate.
  const lo = Math.max(0, target - BEARING_WINDOW_KM);
  const hi = Math.min(phase.totalKm, target + BEARING_WINDOW_KM);
  const behind = positionAtKm(phase.path, phase.cumKm, lo);
  const ahead = positionAtKm(phase.path, phase.cumKm, hi);
  const degenerate = behind[0] === ahead[0] && behind[1] === ahead[1];
  let heading: number;
  if (degenerate) {
    const i = segmentIndexAt(phase.cumKm, Math.min(Math.max(target, 0), phase.totalKm));
    heading = bearingDeg(phase.path[i - 1], phase.path[i]);
  } else {
    heading = bearingDeg(behind, ahead);
  }

  return { lng, lat, bearingDeg: heading, moving: true };
}

/** Margin (degrees) around each mirror boundary (180°, and 0°/360°) within
 *  which the previous mirror state is kept rather than recomputed. Real
 *  track geometry crosses these boundaries thousands of times per journey;
 *  without hysteresis the sprite flips horizontally back and forth. */
const MIRROR_HYSTERESIS_DEG = 12;

/** The rider SVG faces east. Marker rotation is bearing−90; for westward
 *  headings we mirror horizontally (inner scaleX(-1), rotation bearing−270)
 *  so the train never rides upside down. Due north/south never mirror.
 *  `prevMirror` is held near either boundary (180°, and 0°/360°) so a
 *  heading hovering right at the edge can't flap the sprite every frame. */
export function riderTransform(
  bearing: number,
  prevMirror = false,
): { rotateDeg: number; mirror: boolean } {
  const b = ((bearing % 360) + 360) % 360;
  const nearBoundary =
    (b > 180 - MIRROR_HYSTERESIS_DEG && b < 180 + MIRROR_HYSTERESIS_DEG) ||
    b > 360 - MIRROR_HYSTERESIS_DEG ||
    b < MIRROR_HYSTERESIS_DEG;
  const mirror = nearBoundary ? prevMirror : b > 180;
  return { rotateDeg: mirror ? b - 270 : b - 90, mirror };
}

/** Exponentially approaches `target` (degrees) from `prev` along the
 *  shortest angular arc — so 350° → 10° turns forward through 360/0, never
 *  backwards through 180. `tauMs` is the time constant: after `dtMs` the
 *  remaining gap shrinks by a factor of exp(-dtMs/tauMs). `prev === null`
 *  (no prior heading — e.g. the first animation frame of a new journey)
 *  returns `target` immediately rather than spinning up from nothing.
 *  Result is normalized to [0, 360). */
export function smoothBearing(
  prev: number | null,
  target: number,
  dtMs: number,
  tauMs = 140,
): number {
  const norm = (x: number) => ((x % 360) + 360) % 360;
  const t = norm(target);
  if (prev === null) return t;
  const p = norm(prev);
  const diff = (((t - p + 180) % 360) + 360) % 360 - 180; // shortest arc, (-180, 180]
  const alpha = 1 - Math.exp(-dtMs / tauMs);
  return norm(p + diff * alpha);
}
