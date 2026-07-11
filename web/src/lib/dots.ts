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
 * Draw a 5-point star on a canvas for use with map.addImage().
 * Grey fill (#9ca3af) matching the dot palette, subtle white outline.
 */
export function drawStarIcon(size: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const cx = size / 2;
  const cy = size / 2;
  const outerR = size / 2 - 1;
  const innerR = outerR * 0.4;
  const points = 5;

  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const r = i % 2 === 0 ? outerR : innerR;
    const angle = (Math.PI / points) * i - Math.PI / 2;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();
  ctx.fillStyle = "#9ca3af";
  ctx.fill();
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 1.5;
  ctx.stroke();
  return canvas;
}
