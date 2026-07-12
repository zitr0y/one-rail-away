// Mascot-rider geometry & timing: pure helpers, no MapLibre/DOM.
// Spec: docs/superpowers/specs/2026-07-12-branding-phase2-design.md §Mascot rider.

/** One full origin→destination traverse, regardless of journey length.
 *  TUNING POINT: the user is explicitly unsure about fixed duration for long
 *  and short journeys alike ("we shall find out", 2026-07-12). If fixed feels
 *  wrong on the real map, the prepared fallback is mild scaling with path
 *  length (~5–10 s clamped). Judged on the real map by the user. */
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
  let i = 1;
  while (i < phase.cumKm.length - 1 && phase.cumKm[i] < target) i++;
  const a = phase.path[i - 1];
  const b = phase.path[i];
  const segLen = phase.cumKm[i] - phase.cumKm[i - 1];
  const g = segLen === 0 ? 0 : (target - phase.cumKm[i - 1]) / segLen;
  return {
    lng: a[0] + (b[0] - a[0]) * g,
    lat: a[1] + (b[1] - a[1]) * g,
    bearingDeg: bearingDeg(a, b),
    moving: true,
  };
}

/** The rider SVG faces east. Marker rotation is bearing−90; for westward
 *  headings we mirror horizontally (inner scaleX(-1), rotation bearing−270)
 *  so the train never rides upside down. Due north/south never mirror. */
export function riderTransform(bearing: number): { rotateDeg: number; mirror: boolean } {
  const b = ((bearing % 360) + 360) % 360;
  const mirror = b > 180;
  return { rotateDeg: mirror ? b - 270 : b - 90, mirror };
}
