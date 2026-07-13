import type { CityGroups } from "./types";

export interface CityLookup {
  cityForStation: (stationId: string) => string | undefined;
  memberIds: (city: string) => string[];
}

/** Build the bidirectional city lookup once when cities.json is loaded. */
export function buildCityLookup(groups: CityGroups): CityLookup {
  const cityByStationId = new Map<string, string>();
  for (const [city, ids] of Object.entries(groups)) {
    for (const id of ids) cityByStationId.set(id, city);
  }

  return {
    cityForStation: (stationId) => cityByStationId.get(stationId),
    memberIds: (city) => groups[city] ?? [],
  };
}
