// Pure helpers for the unified journey planner. No React, unit-testable.
// Spec: docs/superpowers/specs/2026-07-12-unified-planner-panel-design.md.
import type { ReachFile, Station } from "./types";

/** Fold diacritics + lowercase so "zur" matches "Zürich", "munch" → "München".
 *  Mirrors the server's NFKD-to-base-letter folding (ö→o, not ö→oe). */
export function norm(s: string): string {
  // ̀-ͯ = combining diacritical marks left after NFD decomposition.
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export type DestGroup = "Nonstop" | "One stop" | "Two stops" | "Not reachable";
const GROUP_BY_TRAINS: DestGroup[] = ["Nonstop", "One stop", "Two stops"];
export const GROUP_ORDER: DestGroup[] = ["Nonstop", "One stop", "Two stops", "Not reachable"];

export interface FieldOption {
  station: Station;
  group: DestGroup | ""; // "" = ungrouped (the From field)
  disabled: boolean; // grayed + non-selectable (beyond current filter / unreachable)
}

/** Wrap plain search results (the From field) as ungrouped, selectable options. */
export function toFieldOptions(stations: Station[]): FieldOption[] {
  return stations.map((station) => ({ station, group: "" as const, disabled: false }));
}

/**
 * To-field options for the current origin, grouped by the minimum number of
 * trains needed to reach each match within the time cap. Searches ALL stations
 * (so genuinely unreachable ones can be shown as "Not reachable"). Every
 * reachable option is selectable regardless of the current stop filter — picking
 * one bumps the filter to accommodate (handled in App); only genuinely
 * unreachable options (not a destination, or over the time cap) are disabled.
 */
export function destOptions(
  reach: ReachFile | null,
  stationsById: Map<string, Station>,
  query: string,
  filterMinutes: number,
  limit = 12,
): FieldOption[] {
  if (!reach) return [];
  const q = norm(query.trim());
  if (q.length < 2) return [];

  const destById = new Map(reach.destinations.map((d) => [d.id, d]));
  const out: FieldOption[] = [];

  for (const s of stationsById.values()) {
    if (s.id === reach.origin) continue; // don't offer the origin as a destination
    if (!norm(s.name).includes(q)) continue;

    const d = destById.get(s.id);
    let group: DestGroup;
    let disabled: boolean;
    if (!d) {
      group = "Not reachable";
      disabled = true;
    } else {
      const within = d.journeys.filter((j) => j.duration_min <= filterMinutes);
      if (within.length === 0) {
        group = "Not reachable"; // reachable, but not within the time cap
        disabled = true;
      } else {
        const minTrains = Math.min(...within.map((j) => j.trains));
        group = GROUP_BY_TRAINS[minTrains - 1] ?? "Two stops";
        disabled = false; // selectable; picking it bumps the stop filter in App
      }
    }
    out.push({ station: s, group, disabled });
  }

  out.sort((a, b) => {
    const ga = GROUP_ORDER.indexOf(a.group as DestGroup);
    const gb = GROUP_ORDER.indexOf(b.group as DestGroup);
    if (ga !== gb) return ga - gb;
    return a.station.name.localeCompare(b.station.name);
  });
  return out.slice(0, limit);
}

/** Swap is only meaningful when both endpoints are set. */
export function swapEnabled(hasOrigin: boolean, hasDest: boolean): boolean {
  return hasOrigin && hasDest;
}

/** The To field is usable only once an origin (and its reach set) exists. */
export function toEnabled(hasOrigin: boolean): boolean {
  return hasOrigin;
}
