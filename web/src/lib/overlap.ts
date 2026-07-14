import { pickFeature, type FeatureHit, type FeaturePick } from "./pickfeature";
import type { Station } from "./types";

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
