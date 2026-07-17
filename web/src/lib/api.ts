import type { CityGroups, CoverageCollection, ReachFile, Station } from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

// Reach files are ~weekly data, so a session-lifetime cache (no TTL) is enough
// to avoid re-downloading + re-parsing the same JSON on a re-click of the same
// origin, an A<->B swap-and-back, or re-picking a city (AX). Failed fetches
// are evicted immediately so a retry actually retries instead of replaying
// the same rejection forever.
const reachCache = new Map<string, Promise<ReachFile>>();

function getReachCached(id: string): Promise<ReachFile> {
  const cached = reachCache.get(id);
  if (cached) return cached;
  const promise = get<ReachFile>(`/api/reach/${id}`);
  promise.catch(() => reachCache.delete(id));
  reachCache.set(id, promise);
  return promise;
}

/** Test-only escape hatch — the cache has no public clear otherwise. */
export function __clearReachCacheForTests(): void {
  reachCache.clear();
}

export const api = {
  getStations: () => get<{ stations: Station[] }>("/api/stations"),
  getReach: getReachCached,
  searchStations: (q: string) =>
    get<{ stations: Station[] }>(`/api/stations/search?q=${encodeURIComponent(q)}`),
  getCoverage: () => get<CoverageCollection>("/api/coverage"),
  getCities: () => get<CityGroups>("/api/cities"),
};

/**
 * Race guard for async selection handlers (AX). Wraps a promise so that only
 * the most-recently-created wrapped promise (per returned `guard` instance)
 * resolves to its value; every earlier one resolves to `undefined` once
 * superseded, regardless of resolve order. Create one `guard` per logical
 * selection (e.g. once per App component) and route every call site that can
 * race — including multi-fetch fan-outs — through it.
 */
export function latestOnly<T>(): (promise: Promise<T>) => Promise<T | undefined> {
  let generation = 0;
  return (promise) => {
    const mine = ++generation;
    return promise.then((value) => (mine === generation ? value : undefined));
  };
}
