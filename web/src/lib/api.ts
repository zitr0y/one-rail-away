import type { CoverageCollection, Meta, ReachFile, Station } from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  getStations: () => get<{ stations: Station[] }>("/api/stations"),
  getReach: (id: string) => get<ReachFile>(`/api/reach/${id}`),
  searchStations: (q: string) =>
    get<{ stations: Station[] }>(`/api/stations/search?q=${encodeURIComponent(q)}`),
  getMeta: () => get<Meta>("/api/meta"),
  getCoverage: () => get<CoverageCollection>("/api/coverage"),
};
