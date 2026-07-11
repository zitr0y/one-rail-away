import { describe, expect, it } from "vitest";
import {
  buildRideTimeline,
  rideStateAt,
  riderTransform,
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
