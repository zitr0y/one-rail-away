// Pure helpers for the unified journey planner. No React, unit-testable.
// Spec: docs/superpowers/specs/2026-07-12-unified-planner-panel-design.md.
import type { CityGroups, ReachFile, Station } from "./types";
import { CITY_EXONYMS, type CityLookup } from "./cities";

/** Fold diacritics + lowercase so "zur" matches "Zürich", "munch" → "München".
 *  Mirrors the server's NFKD-to-base-letter folding (ö→o, not ö→oe). */
export function norm(s: string): string {
  // ̀-ͯ = combining diacritical marks left after NFD decomposition.
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export type DestGroup = "local transit" | "Nonstop" | "One stop" | "Two stops" | "Not reachable";
const GROUP_BY_TRAINS: DestGroup[] = ["Nonstop", "One stop", "Two stops"];
export const GROUP_ORDER: DestGroup[] = [
  "local transit", "Nonstop", "One stop", "Two stops", "Not reachable",
];

export interface StationFieldOption {
  kind: "station";
  station: Station;
  group: DestGroup | ""; // "" = ungrouped (the From field)
  disabled: boolean; // grayed + non-selectable (beyond current filter / unreachable)
}

export interface CityFieldOption {
  kind: "city";
  city: string;
  memberIds: string[];
  label: string;
  group: "";
  disabled: false;
}

export type FieldOption = StationFieldOption | CityFieldOption;

/** Wrap plain search results (the From field) as ungrouped, selectable options. */
export function toFieldOptions(stations: Station[]): FieldOption[] {
  return stations.map((station) => ({
    kind: "station", station, group: "" as const, disabled: false,
  }));
}

/** Matching curated city origins for the From field. */
export function cityOptions(cities: CityGroups, query: string): FieldOption[] {
  const q = norm(query.trim());
  if (q.length < 2) return [];
  return Object.entries(cities)
    .filter(([city]) => (
      norm(city).includes(q) || CITY_EXONYMS[city]?.some((alias) => norm(alias).includes(q))
    ))
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([city, memberIds]) => ({
      kind: "city" as const,
      city,
      memberIds,
      label: `${city} — all stations`,
      group: "" as const,
      disabled: false,
    }));
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
  cities?: CityLookup,
  limit = 12,
): StationFieldOption[] {
  if (!reach) return [];
  const q = norm(query.trim());
  if (q.length < 2) return [];

  const destById = new Map(reach.destinations.map((d) => [d.id, d]));
  const out: StationFieldOption[] = [];

  for (const s of stationsById.values()) {
    if (s.id === reach.origin) continue; // don't offer the origin as a destination
    if (!norm(s.name).includes(q)) continue;

    const d = destById.get(s.id);
    let group: DestGroup;
    let disabled: boolean;
    if (!d) {
      const originCity = cities?.cityForStation(reach.origin);
      if (originCity && originCity === cities?.cityForStation(s.id)) {
        group = "local transit";
        disabled = false;
      } else {
        group = "Not reachable";
        disabled = true;
      }
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
    out.push({ kind: "station", station: s, group, disabled });
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
