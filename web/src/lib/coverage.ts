// Pure helpers for the country-coverage veil.
// Spec: docs/superpowers/specs/2026-07-11-veil-rework-design.md §3.
// The veil source is now a single dissolved MultiPolygon (no per-country
// features), so the old filter and per-country tooltip are gone. The tooltip
// is a generic constant; the legend entry is removed (tooltip is the only
// explanation).

// Generic tooltip shown on hover over the veil (spec §3, exact copy).
export const VEIL_TOOLTIP_LIGHT =
  "Reachable by international trains, but we don't yet have data from this country's rail providers.";
export const VEIL_TOOLTIP_DARK =
  "We don't yet have train data for this country.";

export function veilTooltip(tier?: string): string {
  return tier === "light" ? VEIL_TOOLTIP_LIGHT : VEIL_TOOLTIP_DARK;
}

// Hover precedence: the veil tooltip appears only when no station/dot feature is
// under the cursor, so it never competes with the click-selection layers
// (pickfeature.ts precedence stays untouched). `stationHitCount` is the number of
// reach-dots/all-stations features MapLibre reports under the cursor.
export function showVeilTooltip(stationHitCount: number): boolean {
  return stationHitCount === 0;
}
