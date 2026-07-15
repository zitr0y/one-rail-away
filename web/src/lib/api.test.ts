// Backlog AX: session-lifetime reach cache + race guard for reach selections.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { __clearReachCacheForTests, api, latestOnly } from "./api";
import type { ReachFile } from "./types";

const reachFile = (origin: string): ReachFile => ({
  origin, computed_at: "2026-07-13", sample_date: "2026-07-14", destinations: [],
});

function mockFetchOk(data: unknown) {
  return vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(data) });
}

describe("api.getReach cache", () => {
  beforeEach(() => {
    __clearReachCacheForTests();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the same in-flight/resolved promise on a repeat call (no second fetch)", async () => {
    const fetchMock = mockFetchOk(reachFile("berlin-hbf"));
    vi.stubGlobal("fetch", fetchMock);

    const first = api.getReach("berlin-hbf");
    const second = api.getReach("berlin-hbf");

    expect(second).toBe(first); // same cached promise, not just equal data
    await expect(first).resolves.toEqual(reachFile("berlin-hbf"));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // A third call after the promise has settled must still hit the cache.
    await api.getReach("berlin-hbf");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("fetches independently for different ids", async () => {
    const fetchMock = mockFetchOk(reachFile("x"));
    vi.stubGlobal("fetch", fetchMock);

    await api.getReach("paris-nord");
    await api.getReach("amsterdam-centraal");

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("evicts the cache entry on failure so a retry actually refetches", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 500, text: () => Promise.resolve("boom") })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(reachFile("koln-hbf")) });
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getReach("koln-hbf")).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Retry after failure must issue a fresh fetch, not replay the rejection.
    await expect(api.getReach("koln-hbf")).resolves.toEqual(reachFile("koln-hbf"));
    expect(fetchMock).toHaveBeenCalledTimes(2);

    // ...and the successful result is now cached.
    await api.getReach("koln-hbf");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("latestOnly", () => {
  it("resolves a single call with its value", async () => {
    const guard = latestOnly<string>();
    await expect(guard(Promise.resolve("a"))).resolves.toBe("a");
  });

  it("applies only the latest-requested call's result, regardless of resolve order", async () => {
    const guard = latestOnly<string>();

    let resolveA!: (v: string) => void;
    let resolveB!: (v: string) => void;
    const a = new Promise<string>((resolve) => { resolveA = resolve; });
    const b = new Promise<string>((resolve) => { resolveB = resolve; });

    // Two "quick selections" in a row: A requested first, then B supersedes it.
    const guardedA = guard(a);
    const guardedB = guard(b);

    // B (the newer request) resolves first...
    resolveB("b-result");
    // ...then A (the older, superseded request) resolves after it.
    resolveA("a-result");

    expect(await guardedB).toBe("b-result");
    expect(await guardedA).toBeUndefined(); // superseded — must not win
  });

  it("also guards a later call when the earlier one resolves first", async () => {
    const guard = latestOnly<string>();

    const guardedA = guard(Promise.resolve("a-result"));
    await guardedA; // let A resolve and "apply" before B is even requested
    const guardedB = guard(Promise.resolve("b-result"));

    expect(await guardedA).toBe("a-result");
    expect(await guardedB).toBe("b-result");
  });
});
