import { describe, expect, it } from "vitest";
import {
  buildRideTimeline,
  rideStateAt,
  riderTransform,
  smoothBearing,
  positionAtKm,
  TRAVERSE_MS,
  TRANSFER_PAUSE_MS,
  REST_MS,
} from "./ride";

// Two straight legs along the equator: A(0,0)→B(1,0), transfer, B(1,0)→C(4,0).
// Leg lengths 1° : 3° → move time splits 25% / 75%.
const LEGS: [number, number][][] = [
  [[0, 0], [1, 0]],
  [[1, 0], [4, 0]],
];

describe("buildRideTimeline", () => {
  it("splits TRAVERSE_MS across legs proportional to length, with pauses", () => {
    const tl = buildRideTimeline(LEGS)!;
    // move(1750) + transfer(500) + move(5250) + rest(1000)
    expect(tl.totalMs).toBe(TRAVERSE_MS + TRANSFER_PAUSE_MS + REST_MS);
    expect(tl.phases.map((p) => p.kind)).toEqual(["move", "dwell", "move", "dwell"]);
    expect(tl.phases[0].endMs - tl.phases[0].startMs).toBeCloseTo(TRAVERSE_MS * 0.25, 5);
    expect(tl.phases[2].endMs - tl.phases[2].startMs).toBeCloseTo(TRAVERSE_MS * 0.75, 5);
  });

  it("returns null for empty or zero-length paths", () => {
    expect(buildRideTimeline([])).toBeNull();
    expect(buildRideTimeline([[[2, 2], [2, 2]]])).toBeNull();
  });
});

describe("rideStateAt", () => {
  const tl = buildRideTimeline(LEGS)!;

  it("starts at the origin, moving east (bearing 90)", () => {
    const s = rideStateAt(tl, 0);
    expect(s.lng).toBeCloseTo(0, 6);
    expect(s.lat).toBeCloseTo(0, 6);
    expect(s.bearingDeg).toBeCloseTo(90, 3);
    expect(s.moving).toBe(true);
  });

  it("is halfway along leg 1 at half of leg 1's move time", () => {
    const s = rideStateAt(tl, (TRAVERSE_MS * 0.25) / 2);
    expect(s.lng).toBeCloseTo(0.5, 3);
    expect(s.moving).toBe(true);
  });

  it("eases in: lags behind linear early in a leg (gradual acceleration)", () => {
    // 25% through leg 1's move time. Linear would be lng 0.25; smoothstep(0.25)
    // = 0.15625, so the rider is still building speed away from the origin.
    const s = rideStateAt(tl, TRAVERSE_MS * 0.25 * 0.25);
    expect(s.lng).toBeLessThan(0.25);
    expect(s.lng).toBeCloseTo(0.15625, 5);
  });

  it("pins to the transfer station during the transfer dwell", () => {
    const s = rideStateAt(tl, TRAVERSE_MS * 0.25 + TRANSFER_PAUSE_MS / 2);
    expect(s.lng).toBeCloseTo(1, 6);
    expect(s.lat).toBeCloseTo(0, 6);
    expect(s.moving).toBe(false);
  });

  it("rests at the destination at the end, then wraps around (loop)", () => {
    const atRest = rideStateAt(tl, tl.totalMs - 1);
    expect(atRest.lng).toBeCloseTo(4, 6);
    expect(atRest.moving).toBe(false);
    const wrapped = rideStateAt(tl, tl.totalMs + 5);
    expect(wrapped.lng).toBeCloseTo(rideStateAt(tl, 5).lng, 9);
  });
});

describe("riderTransform", () => {
  it("east: no rotation, no mirror", () => {
    expect(riderTransform(90)).toEqual({ rotateDeg: 0, mirror: false });
  });
  it("west: mirrored, no rotation", () => {
    expect(riderTransform(270)).toEqual({ rotateDeg: 0, mirror: true });
  });
  it("north-east climbs counterclockwise", () => {
    expect(riderTransform(45)).toEqual({ rotateDeg: -45, mirror: false });
  });
  it("south-west mirrors then climbs", () => {
    expect(riderTransform(225)).toEqual({ rotateDeg: -45, mirror: true });
  });
  it("due north/south never mirror", () => {
    expect(riderTransform(0)).toEqual({ rotateDeg: -90, mirror: false });
    expect(riderTransform(180)).toEqual({ rotateDeg: 90, mirror: false });
  });
  it("normalizes out-of-range bearings", () => {
    expect(riderTransform(450)).toEqual({ rotateDeg: 0, mirror: false }); // 450 ≡ 90
    expect(riderTransform(-90)).toEqual({ rotateDeg: 0, mirror: true }); // -90 ≡ 270
  });
});

describe("riderTransform hysteresis", () => {
  it("keeps the previous mirror value while oscillating near the 180 boundary", () => {
    // Naive (no hysteresis) would flip here since 185 > 180; hysteresis holds it.
    expect(riderTransform(185, false).mirror).toBe(false);
    // Naive would un-flip here since 179 < 180; hysteresis holds it mirrored.
    expect(riderTransform(179, true).mirror).toBe(true);
  });

  it("still flips once well past the 180 boundary, regardless of prior state", () => {
    expect(riderTransform(210, false).mirror).toBe(true);
    expect(riderTransform(150, true).mirror).toBe(false);
  });

  it("keeps the previous mirror value while oscillating near the 0/360 boundary", () => {
    // Naive would flip here since 355 > 180; hysteresis holds it un-mirrored.
    expect(riderTransform(355, false).mirror).toBe(false);
    // Naive would un-flip here since 5 < 180; hysteresis holds it mirrored.
    expect(riderTransform(5, true).mirror).toBe(true);
  });
});

describe("positionAtKm", () => {
  it("interpolates along the polyline and clamps to both ends", () => {
    const path: [number, number][] = [[0, 0], [1, 0], [1, 1]];
    const tl = buildRideTimeline([path])!;
    const phase = tl.phases[0];
    if (phase.kind !== "move") throw new Error("expected a move phase");
    expect(positionAtKm(path, phase.cumKm, 0)).toEqual([0, 0]);
    expect(positionAtKm(path, phase.cumKm, phase.totalKm)).toEqual([1, 1]);
    expect(positionAtKm(path, phase.cumKm, -5)).toEqual([0, 0]); // clamps below
    expect(positionAtKm(path, phase.cumKm, phase.totalKm + 5)).toEqual([1, 1]); // clamps above
    const mid = positionAtKm(path, phase.cumKm, phase.cumKm[1] / 2);
    expect(mid[0]).toBeCloseTo(0.5, 6);
    expect(mid[1]).toBeCloseTo(0, 6);
  });
});

describe("rideStateAt heading (look-ahead smoothing over real track geometry)", () => {
  it("ignores tiny lateral jitter that would swing the old per-segment bearing wildly", () => {
    const dLon = 0.0002; // ~22 m forward step at the equator
    const dLat = 0.00015; // ~17 m lateral jitter, alternating side to side
    const steps = 60; // ~1.6 km total: comfortably more than 2*BEARING_WINDOW_KM
    const path: [number, number][] = [[0, 0]];
    for (let i = 1; i <= steps; i++) {
      const lat = i % 2 === 0 ? 0 : dLat;
      path.push([path[i - 1][0] + dLon, lat]);
    }

    // Prove the fixture itself has wild per-segment swings — this is the old bug,
    // verified directly on the data, not by calling the (fixed) production code.
    const rawBearing = (a: [number, number], b: [number, number]) => {
      const midLatRad = (((a[1] + b[1]) / 2) * Math.PI) / 180;
      const dx = (b[0] - a[0]) * Math.cos(midLatRad);
      const dy = b[1] - a[1];
      return (Math.atan2(dx, dy) * 180) / Math.PI;
    };
    let maxSwing = 0;
    for (let i = 2; i < path.length; i++) {
      const b1 = rawBearing(path[i - 2], path[i - 1]);
      const b2 = rawBearing(path[i - 1], path[i]);
      maxSwing = Math.max(maxSwing, Math.abs(b2 - b1));
    }
    expect(maxSwing).toBeGreaterThan(30); // genuinely wild consecutive-segment swings

    const tl = buildRideTimeline([path])!;
    const samples = [0.3, 0.4, 0.5, 0.6, 0.7].map(
      (f) => rideStateAt(tl, tl.totalMs * f).bearingDeg,
    );
    for (const b of samples) {
      expect(Math.abs(b - 90)).toBeLessThan(15);
    }
  });

  it("does not let a leading station stub dominate the heading at the start of a leg", () => {
    const stubLat = 0.0001; // ~11 m, perpendicular stub off the platform
    const legKm = 1; // long straight run east after the stub
    const dLonBig = legKm / (111.32 * Math.cos((stubLat * Math.PI) / 180));
    const path: [number, number][] = [
      [0, 0],
      [0, stubLat], // stub: due north, perpendicular to the eastward run
      [dLonBig, stubLat], // ~1 km due east
    ];
    const tl = buildRideTimeline([path])!;
    const s = rideStateAt(tl, 0);
    // The raw leading segment alone points due north (~0°); the look-ahead
    // window should instead reflect the eastward run (~90°).
    expect(Math.abs(s.bearingDeg - 90)).toBeLessThan(20);
  });

  it("handles a leg where every point is identical without a NaN heading", () => {
    const identicalLeg: [number, number][] = [[5, 5], [5, 5], [5, 5]];
    const tl = buildRideTimeline([[[0, 0], [1, 0]], identicalLeg])!;
    const s = rideStateAt(tl, tl.totalMs - 1); // final rest, at the identical-point leg's end
    expect(Number.isFinite(s.bearingDeg)).toBe(true);
    expect(s.lng).toBeCloseTo(5, 6);
  });

  it("handles a 2-point leg much shorter than the bearing look-ahead window", () => {
    const shortLeg: [number, number][] = [[0, 0], [0.0001, 0]]; // ~11 m
    const tl = buildRideTimeline([shortLeg, [[0.0001, 0], [0.0002, 0]]])!;
    const s = rideStateAt(tl, tl.phases[0].startMs + 1);
    expect(Number.isFinite(s.bearingDeg)).toBe(true);
    expect(Number.isFinite(s.lng)).toBe(true);
    expect(Number.isFinite(s.lat)).toBe(true);
  });
});

describe("smoothBearing", () => {
  it("returns the target immediately when there is no previous heading", () => {
    expect(smoothBearing(null, 42, 16)).toBe(42);
    expect(smoothBearing(null, 358, 1000)).toBe(358);
  });

  it("takes the shortest arc across the 0/360 wrap, never through 180", () => {
    const b = smoothBearing(350, 10, 50);
    expect(b).toBeGreaterThanOrEqual(0);
    expect(b).toBeLessThan(360);
    // Moving from 350 toward 10 the short way passes through 360/0, so the
    // result must land near that wrap (>350 or <10) — never in the 180-ish
    // "long way around" range.
    expect(b > 350 || b < 10).toBe(true);
  });

  it("approaches the target asymptotically and stays in [0, 360)", () => {
    let b: number | null = null;
    for (let i = 0; i < 50; i++) {
      b = smoothBearing(b, 270, 16);
    }
    expect(b).not.toBeNull();
    expect(b!).toBeGreaterThanOrEqual(0);
    expect(b!).toBeLessThan(360);
    expect(b!).toBeCloseTo(270, 0);
  });
});
