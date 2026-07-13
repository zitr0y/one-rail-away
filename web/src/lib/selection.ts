// Pure selection helpers — logic unit-testable without React or MapLibre.
// Spec: docs/superpowers/specs/2026-07-11-selection-ux-design.md §3.

/**
 * Decide what an empty-map click (no station under cursor) should do.
 * Mirrors the Escape key step-back behaviour:
 *   journey card open → clear destination only (back to the full fan)
 *   origin selected   → clear everything
 *   nothing selected  → noop
 */
export function emptyClickAction(
  hasDest: boolean,
  hasOrigin: boolean,
): "clearDest" | "clearAll" | "noop" {
  if (hasDest) return "clearDest";
  if (hasOrigin) return "clearAll";
  return "noop";
}

/** Decide whether clearing an origin promotes its selected destination. */
export function clearOriginAction(
  selectedDest: string | null,
): { promote: string } | { clearAll: true } {
  return selectedDest === null ? { clearAll: true } : { promote: selectedDest };
}

/**
 * After swapping origin and destination, check whether the old origin
 * appears among the *new* origin's destinations.
 * Returns the old origin's id if present, or null to fall back to
 * origin-only (no destination selected, no error shown).
 */
export function swapDest(
  destinations: { id: string }[],
  oldOriginId: string,
): string | null {
  return destinations.some((d) => d.id === oldOriginId) ? oldOriginId : null;
}
