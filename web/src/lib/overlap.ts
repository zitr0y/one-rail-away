import { pickFeature, type FeatureHit, type FeaturePick } from "./pickfeature";
import type { MaxTrains } from "./geojson";
import type { ReachFile, Station } from "./types";

export interface StationChoice {
  pick: FeaturePick;
  name: string;
  nDest: number;
}

/**
 * Turn rendered station hits into the choices for an overlap click. One
 * station can appear in more than one layer; pickFeature preserves the normal
 * reach-dot/capital/all-station priority for that station before choices are
 * sorted by their visible name.
 */
export function overlapStationChoices(hits: FeatureHit[], stations: Station[]): StationChoice[] {
  const hitsById = new Map<string, FeatureHit[]>();
  for (const hit of hits) {
    const stationHits = hitsById.get(hit.id) ?? [];
    stationHits.push(hit);
    hitsById.set(hit.id, stationHits);
  }
  const stationsById = new Map(stations.map((station) => [station.id, station]));
  const choices: StationChoice[] = [];
  for (const [id, stationHits] of hitsById) {
    const pick = pickFeature(stationHits);
    const station = stationsById.get(id);
    if (pick && station) choices.push({ pick, name: station.name, nDest: station.n_dest ?? 0 });
  }
  return choices.sort((a, b) =>
    b.nDest - a.nDest
    || a.name.localeCompare(b.name, undefined, { sensitivity: "base" })
    || a.pick.id.localeCompare(b.pick.id));
}

export interface TargetChoice extends StationChoice {
  /** Fewest trains from the current origin under active filters; null = unreachable. */
  minTrains: number | null;
}

/** Fewest trains per destination among journeys within BOTH active filters.
 *  Deliberately not bestJourney(): that is the fastest journey, whose train
 *  count can exceed the minimum (backlog AE — "steps to reach"). */
export function reachableMinTrains(
  reach: ReachFile | null, maxTrains: MaxTrains, maxMinutes: number,
): Map<string, number> {
  const result = new Map<string, number>();
  if (!reach) return result;
  for (const d of reach.destinations) {
    const eligible = d.journeys.filter(
      (j) => j.trains <= maxTrains && j.duration_min <= maxMinutes);
    if (eligible.length) result.set(d.id, Math.min(...eligible.map((j) => j.trains)));
  }
  return result;
}

/** Fewest trains per destination among journeys in the raw reach data (without filter constraints). */
export function rawMinTrains(reach: ReachFile | null): Map<string, number> {
  const result = new Map<string, number>();
  if (!reach) return result;
  for (const d of reach.destinations) {
    if (d.journeys.length) {
      result.set(d.id, Math.min(...d.journeys.map((j) => j.trains)));
    }
  }
  return result;
}

/** Target-mode ordering (backlog AE): reachable first by fewest trains, then
 *  connection count; unreachable last, muted but still selectable. */
export function rankTargetChoices(
  choices: StationChoice[],
  minTrainsFiltered: Map<string, number>,
  minTrainsRaw: Map<string, number>,
): TargetChoice[] {
  return choices
    .map((c) => ({ ...c, minTrains: minTrainsFiltered.get(c.pick.id) ?? null }))
    .sort((a, b) => {
      const aRawTrains = minTrainsRaw.get(a.pick.id) ?? null;
      const bRawTrains = minTrainsRaw.get(b.pick.id) ?? null;

      if ((aRawTrains === null) !== (bRawTrains === null)) {
        return aRawTrains === null ? 1 : -1;
      }
      if (aRawTrains !== null && bRawTrains !== null && aRawTrains !== bRawTrains) {
        return aRawTrains - bRawTrains;
      }
      return b.nDest - a.nDest
        || a.name.localeCompare(b.name, undefined, { sensitivity: "base" })
        || a.pick.id.localeCompare(b.pick.id);
    });
}

