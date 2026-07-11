// Pure helpers for the country-coverage veil.
// Spec: docs/superpowers/specs/2026-07-11-country-greying-design.md §3.
// Kept out of Map.tsx so the filter expression, tooltip copy, and hover-precedence
// rule are unit-testable without a live map.

// Exact legend copy (spec §3). Defined here so the wording is asserted in one place.
export const VEIL_LEGEND = "Grey countries: not yet in our system";

// MapLibre fill-layer filter: show the veil only over non-covered countries.
export type VeilFilter = ["==", ["get", "covered"], boolean];
export function veilFilter(): VeilFilter {
  return ["==", ["get", "covered"], false];
}

// Tooltip text for a hovered grey country (spec §3, exact copy; em dash U+2014).
export function coverageTooltip(name: string): string {
  return `${name} — not yet in our system`;
}

// Hover precedence: the veil tooltip appears only when no station/dot feature is
// under the cursor, so it never competes with the click-selection layers
// (pickfeature.ts precedence stays untouched). `stationHitCount` is the number of
// reach-dots/all-stations features MapLibre reports under the cursor.
export function showVeilTooltip(stationHitCount: number): boolean {
  return stationHitCount === 0;
}
