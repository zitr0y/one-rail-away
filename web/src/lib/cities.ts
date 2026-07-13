import type { CityGroups } from "./types";

/** English/common city names used to expand native-name city search matches. */
export const CITY_EXONYMS: Record<string, readonly string[]> = {
  Bruxelles: ["Brussels"],
  Wien: ["Vienna"],
  Köln: ["Cologne"],
  Warszawa: ["Warsaw"],
  Praha: ["Prague"],
  København: ["Copenhagen"],
  Zürich: ["Zurich"],
  "Den Haag": ["The Hague"],
  München: ["Munich"],
};

export interface CityLookup {
  cityForStation: (stationId: string) => string | undefined;
  memberIds: (city: string) => string[];
}

/** Return a multi-station city group for an origin-selection popup. */
export function cityForStation(
  id: string, cityGroups: CityGroups,
): { city: string; memberIds: string[] } | null {
  for (const [city, memberIds] of Object.entries(cityGroups)) {
    if (memberIds.length >= 2 && memberIds.includes(id)) return { city, memberIds };
  }
  return null;
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
