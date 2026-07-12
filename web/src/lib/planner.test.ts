import { describe, expect, it } from "vitest";
import { destOptions, norm, swapEnabled, toEnabled, toFieldOptions } from "./planner";
import type { Journey, ReachFile, Station } from "./types";

const st = (id: string, name: string): Station => ({
  id, name, lat: 0, lon: 0, country: "NL", has_reach: true,
});
const jrny = (trains: number, duration_min: number): Journey => ({ trains, duration_min, legs: [] });

const stationsById = new Map<string, Station>([
  ["o", st("o", "Nijmegen")],
  ["arn", st("arn", "Arnhem Centraal")],
  ["aar", st("aar", "Aarhus H")],
  ["war", st("war", "Warszawa Centralna")],
  ["bcn", st("bcn", "Barcelona Sants")], // in the map but NOT a destination
  ["zur", st("zur", "Zürich HB")],
]);

const reach: ReachFile = {
  origin: "o", computed_at: "", sample_date: "",
  destinations: [
    { id: "arn", direct_per_day: 20, journeys: [jrny(1, 20)] },
    { id: "aar", direct_per_day: 2, journeys: [jrny(2, 400)] },
    { id: "war", direct_per_day: 1, journeys: [jrny(2, 800)] },
    { id: "zur", direct_per_day: 3, journeys: [jrny(1, 300)] },
  ],
};

describe("norm", () => {
  it("folds diacritics and lowercases", () => {
    expect(norm("Zürich")).toBe("zurich");
    expect(norm("MÜNCHEN")).toBe("munchen");
  });
});

describe("destOptions", () => {
  it("groups by min trains and disables options beyond the current filter", () => {
    // "ar" matches Arnhem, Aarhus, Warszawa, Barcelona (not Nijmegen origin).
    const opts = destOptions(reach, stationsById, "ar", 1, Infinity);
    expect(opts.map((o) => [o.station.id, o.group, o.disabled])).toEqual([
      ["arn", "Nonstop", false], // reachable nonstop → selectable
      ["aar", "One stop", true], // needs 2 trains, filter is nonstop → grayed
      ["war", "One stop", true],
      ["bcn", "Not reachable", true], // not a destination at all
    ]);
  });

  it("enables the one-stop options when the filter allows two trains", () => {
    const opts = destOptions(reach, stationsById, "ar", 2, Infinity);
    const byId = Object.fromEntries(opts.map((o) => [o.station.id, o.disabled]));
    expect(byId).toEqual({ arn: false, aar: false, war: false, bcn: true });
  });

  it("marks a destination over the time cap as Not reachable", () => {
    const opts = destOptions(reach, stationsById, "warszawa", 3, 600); // 800 min > 600
    expect(opts).toHaveLength(1);
    expect(opts[0].group).toBe("Not reachable");
    expect(opts[0].disabled).toBe(true);
  });

  it("matches diacritics-insensitively", () => {
    const opts = destOptions(reach, stationsById, "zur", 1, Infinity);
    expect(opts.map((o) => o.station.id)).toEqual(["zur"]);
  });

  it("is empty for a short query or when there is no reach", () => {
    expect(destOptions(reach, stationsById, "a", 3, Infinity)).toEqual([]);
    expect(destOptions(null, stationsById, "arnhem", 3, Infinity)).toEqual([]);
  });
});

describe("toFieldOptions", () => {
  it("wraps stations as ungrouped selectable options", () => {
    expect(toFieldOptions([st("x", "X")])).toEqual([{ station: st("x", "X"), group: "", disabled: false }]);
  });
});

describe("swapEnabled / toEnabled", () => {
  it("swap needs both endpoints", () => {
    expect(swapEnabled(true, true)).toBe(true);
    expect(swapEnabled(true, false)).toBe(false);
    expect(swapEnabled(false, true)).toBe(false);
  });
  it("To needs an origin", () => {
    expect(toEnabled(true)).toBe(true);
    expect(toEnabled(false)).toBe(false);
  });
});
