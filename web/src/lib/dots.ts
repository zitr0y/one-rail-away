// Pure helpers for dot sizing and the capital star icon.
// Spec: docs/superpowers/specs/2026-07-11-dots-clustering-design.md §2–4.

import type { ExpressionSpecification } from "maplibre-gl";

/**
 * Data-driven circle-radius for the grey all-stations layer, driven by
 * n_routes = distinct train routes calling at the station (hub value).
 * Calibrated on the 2026-07-11 build: p50=3, p90=16, p99=42, max=74 —
 * most dots stay small (p50 -> ~2.9px), only true hubs reach 8px.
 */
export function dotRadiusExpression(): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["sqrt", ["max", ["get", "n_routes"], 0]],
    0, 2,
    2, 3,
    5, 5,
    Math.sqrt(74), 8,
  ] as ExpressionSpecification;
}

/**
 * Rasterize a 5-point star for map.addImage() as {width, height, data} —
 * one of addImage's accepted shapes (a raw canvas element is NOT: passing one
 * throws and aborts the whole map load handler). Pure math, no DOM/canvas, so
 * it behaves identically in the browser and in tests.
 * Dark grey fill (#4b5563) so capitals stand out from the dot palette; white rim.
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
      data[o] = grey ? 75 : 255;
      data[o + 1] = grey ? 85 : 255;
      data[o + 2] = grey ? 99 : 255;
      data[o + 3] = 255;
    }
  }
  return { width: size, height: size, data };
}
