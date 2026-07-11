// Pure helpers for dot sizing, cluster rendering, and star icons.
// Spec: docs/superpowers/specs/2026-07-11-dots-clustering-design.md §2–4.

import type { ExpressionSpecification } from "maplibre-gl";

/**
 * Data-driven circle-radius for the grey all-stations layer.
 * sqrt scale from 2.5px (n_dest=0) to 8px, clamped at n_dest=400.
 * sqrt(0)=0, sqrt(400)=20 — we interpolate linearly in sqrt-space.
 */
export function dotRadiusExpression(): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["sqrt", ["max", ["get", "n_dest"], 0]],
    0, 2.5,
    Math.sqrt(400), 8,
  ] as ExpressionSpecification;
}

/**
 * circle-radius for station-clusters bubble, scaled by point_count.
 */
export function clusterRadiusExpression(): ExpressionSpecification {
  return [
    "step",
    ["get", "point_count"],
    15,   // default (2+)
    5, 18,
    10, 22,
    25, 26,
  ] as ExpressionSpecification;
}

/**
 * Sort stations for the cluster pick-list popup:
 * descending n_dest, then ascending name for ties.
 * Returns a new sorted array (does not mutate).
 */
export function sortForClusterList<T extends { name: string; n_dest: number }>(
  stations: T[],
): T[] {
  return [...stations].sort((a, b) =>
    b.n_dest - a.n_dest || a.name.localeCompare(b.name),
  );
}

/**
 * Rasterize a 5-point star for map.addImage() as {width, height, data} —
 * one of addImage's accepted shapes (a raw canvas element is NOT: passing one
 * throws and aborts the whole map load handler). Pure math, no DOM/canvas, so
 * it behaves identically in the browser and in tests.
 * Grey fill (#9ca3af) matching the dot palette, white rim.
 */
export function drawStarIcon(size: number): { width: number; height: number; data: Uint8ClampedArray } {
  const cx = size / 2;
  const cy = size / 2;

  function starVertices(outerR: number): [number, number][] {
    const pts: [number, number][] = [];
    for (let i = 0; i < 10; i++) {
      const r = i % 2 === 0 ? outerR : outerR * 0.4;
      const angle = (Math.PI / 5) * i - Math.PI / 2;
      pts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)]);
    }
    return pts;
  }

  function inside(x: number, y: number, poly: [number, number][]): boolean {
    let odd = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i];
      const [xj, yj] = poly[j];
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) odd = !odd;
    }
    return odd;
  }

  const rim = starVertices(size / 2 - 0.5);
  const fill = starVertices((size / 2 - 0.5) * 0.8);
  const data = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const px = x + 0.5;
      const py = y + 0.5;
      if (!inside(px, py, rim)) continue;
      const o = (y * size + x) * 4;
      const grey = inside(px, py, fill);
      data[o] = grey ? 156 : 255;
      data[o + 1] = grey ? 163 : 255;
      data[o + 2] = grey ? 175 : 255;
      data[o + 3] = 255;
    }
  }
  return { width: size, height: size, data };
}
