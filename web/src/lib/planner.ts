// Pure helpers for the unified journey planner. No React, unit-testable.
// Spec: docs/superpowers/specs/2026-07-12-unified-planner-panel-design.md.
import type { ReachFile, Station } from "./types";

/**
 * Reachable destinations of the current origin whose name matches `query`,
 * resolved to Station objects via `stationsById`. Runs entirely client-side,
 * so the To field can only ever offer stations that are actually reachable.
 * Empty/short queries return nothing (the dropdown only opens on typing).
 */
export function reachableDestOptions(
  reach: ReachFile | null,
  stationsById: Map<string, Station>,
  query: string,
  limit = 8,
): Station[] {
  if (!reach) return [];
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const out: Station[] = [];
  for (const d of reach.destinations) {
    const s = stationsById.get(d.id);
    if (s && s.name.toLowerCase().includes(q)) {
      out.push(s);
      if (out.length >= limit) break;
    }
  }
  return out;
}

/** Swap is only meaningful when both endpoints are set. */
export function swapEnabled(hasOrigin: boolean, hasDest: boolean): boolean {
  return hasOrigin && hasDest;
}

/** The To field is usable only once an origin (and its reach set) exists. */
export function toEnabled(hasOrigin: boolean): boolean {
  return hasOrigin;
}
