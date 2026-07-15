// Pure helpers for dot sizing and the capital star icon.
// Spec: docs/superpowers/specs/2026-07-11-dots-clustering-design.md §2–4.

import type { ExpressionSpecification } from "maplibre-gl";
import type { StationOpacityExpression } from "./highlight";

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
    2, 2.6,
    4, 4.5,
    Math.sqrt(74), 9,
  ] as ExpressionSpecification;
}

/**
 * Fade low-connection stations out at continental zoom levels, then reveal
 * them as the map closes in. TUNING POINTS: 150 / 50 / 10 destinations and
 * zoom 4 / 5.5 / 7 / 9 were chosen to leave only major hubs at a glance.
 * Capital stars and reach dots have separate layers and remain visible.
 */
export function stationDotOpacityByZoom(): ExpressionSpecification {
  return [
    "interpolate", ["linear"], ["zoom"],
    4, ["step", ["get", "n_dest"], 0, 150, 0.7],
    5.5, ["step", ["get", "n_dest"], 0, 50, 0.7],
    7, ["step", ["get", "n_dest"], 0, 10, 0.7],
    9, 0.7,
  ] as ExpressionSpecification;
}

/**
 * Combine zoom decluttering with the reach/journey highlight without nesting
 * `zoom` below another expression. MapLibre only accepts `zoom` as the input
 * to the outermost step or interpolate expression, so each zoom stop gets its
 * own zoom-free id match instead of multiplying the whole interpolation.
 */
export function allStationOpacityExpression(
  alwaysVisibleIds: string[],
  fallbackOpacity: StationOpacityExpression,
): ExpressionSpecification {
  const opacityByZoom = stationDotOpacityByZoom();
  if (alwaysVisibleIds.length === 0) return opacityByZoom;

  return opacityByZoom.map((part, index) => {
    // An interpolate expression has stop/output pairs starting at index 3;
    // outputs are therefore the even indexes from 4 onward.
    if (index < 4 || index % 2 !== 0) return part;
    return [
      "match", ["get", "id"], alwaysVisibleIds, 0.7,
      ["*", part, fallbackOpacity],
    ];
  }) as ExpressionSpecification;
}

/**
 * Reach-destination dots share the hub scale but keep a higher floor so small
 * destinations stay clickable (they sit above the all-stations layer).
 */
export function reachDotRadiusExpression(): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["sqrt", ["max", ["get", "n_routes"], 0]],
    0, 4.5,
    Math.sqrt(74), 9,
  ] as ExpressionSpecification;
}

/**
 * Data-driven icon-size for capital stars: same sqrt(n_routes) hub scale as
 * the dots, so Wien Hbf (74 routes) reads bigger than a quiet capital.
 * 0.55–1.05 of the 22px logical star = ~12px to ~23px.
 */
export function starSizeExpression(): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["sqrt", ["max", ["get", "n_routes"], 0]],
    0, 0.55,
    Math.sqrt(74), 1.05,
  ] as ExpressionSpecification;
}

function insidePolygon(x: number, y: number, poly: [number, number][]): boolean {
  let odd = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) odd = !odd;
  }
  return odd;
}

/**
 * Rasterize an icon for map.addImage() as {width, height, data} — one of
 * addImage's accepted shapes (a raw canvas element is NOT: passing one throws
 * and aborts the whole map load handler). Pixels outside `rim` stay
 * transparent; the rest get the colour `colorAt` picks for the pixel centre.
 * Pure math, no DOM/canvas, so it behaves identically in the browser and in
 * tests.
 */
function rasterizeIcon(
  size: number,
  rim: [number, number][],
  colorAt: (px: number, py: number) => [number, number, number],
): { width: number; height: number; data: Uint8ClampedArray } {
  const data = new Uint8ClampedArray(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const px = x + 0.5;
      const py = y + 0.5;
      if (!insidePolygon(px, py, rim)) continue;
      const o = (y * size + x) * 4;
      const [r, g, b] = colorAt(px, py);
      data[o] = r;
      data[o + 1] = g;
      data[o + 2] = b;
      data[o + 3] = 255;
    }
  }
  return { width: size, height: size, data };
}

/**
 * Rasterize a 5-point star for map.addImage().
 * Brand-gold fill (#FFCC00) with a navy rim (#003399): the EU star, readable on
 * both the warm-paper land and the pale water.
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

  const rim = starVertices(size / 2 - 0.5);
  const fill = starVertices((size / 2 - 0.5) * 0.8);
  return rasterizeIcon(size, rim, (px, py) =>
    insidePolygon(px, py, fill) ? [255, 204, 0] : [0, 51, 153],
  );
}

/**
 * Rasterize a red octagonal stop sign for map.addImage(). Marks a transfer on
 * the selected route — the "stop" where you change trains. Fixed stop-red
 * (#C1121F) with a white rim, legible on both the warm-paper and deep-night
 * basemaps, so it is theme-independent (never retinted, like the capital
 * star).
 */
export function drawStopSignIcon(size: number): { width: number; height: number; data: Uint8ClampedArray } {
  const cx = size / 2;
  const cy = size / 2;

  function octagonVertices(r: number): [number, number][] {
    const pts: [number, number][] = [];
    for (let i = 0; i < 8; i++) {
      const angle = (Math.PI / 4) * i + Math.PI / 8; // flat-topped octagon
      pts.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)]);
    }
    return pts;
  }

  const rim = octagonVertices(size / 2 - 0.5);
  const fill = octagonVertices((size / 2 - 0.5) * 0.82);
  const stripeHalf = size * 0.12; // white horizontal bar through the middle
  // Red field inside a white rim, crossed by a white centre stripe.
  return rasterizeIcon(size, rim, (px, py) =>
    insidePolygon(px, py, fill) && Math.abs(py - cy) > stripeHalf
      ? [193, 18, 31]
      : [255, 255, 255],
  );
}
