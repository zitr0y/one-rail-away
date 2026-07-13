import { describe, expect, it } from "vitest";
import { buildCityLookup } from "./cities";
import { cityOptions, destOptions, norm, swapEnabled, toEnabled, toFieldOptions } from "./planner";
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
  it("groups by min trains; every reachable option is selectable (filter bumps on pick)", () => {
    // "ar" matches Arnhem, Aarhus, Warszawa, Barcelona (not Nijmegen origin).
    const opts = destOptions(reach, stationsById, "ar", Infinity);
    expect(opts.map((o) => [o.station.id, o.group, o.disabled])).toEqual([
      ["arn", "Nonstop", false],
      ["aar", "One stop", false], // needs 2 trains but still selectable
      ["war", "One stop", false],
      ["bcn", "Not reachable", true], // not a destination at all → disabled
    ]);
  });

  it("marks a destination over the time cap as Not reachable (disabled)", () => {
    const opts = destOptions(reach, stationsById, "warszawa", 600); // 800 min > 600
    expect(opts).toHaveLength(1);
    expect(opts[0].group).toBe("Not reachable");
    expect(opts[0].disabled).toBe(true);
  });

  it("matches diacritics-insensitively", () => {
    const opts = destOptions(reach, stationsById, "zur", Infinity);
    expect(opts.map((o) => o.station.id)).toEqual(["zur"]);
  });

  it("is empty for a short query or when there is no reach", () => {
    expect(destOptions(reach, stationsById, "a", Infinity)).toEqual([]);
    expect(destOptions(null, stationsById, "arnhem", Infinity)).toEqual([]);
  });

  it("labels an unreachable same-city sibling as local transit", () => {
    const stations = new Map([
      ["paris-nord", st("paris-nord", "Paris Gare du Nord")],
      ["paris-lyon", st("paris-lyon", "Paris Gare de Lyon")],
    ]);
    const localReach: ReachFile = {
      origin: "paris-nord", computed_at: "", sample_date: "", destinations: [],
    };
    const cities = buildCityLookup({ Paris: ["paris-nord", "paris-lyon"] });

    expect(destOptions(localReach, stations, "lyon", Infinity, cities)).toMatchObject([
      { station: { id: "paris-lyon" }, group: "local transit", disabled: false },
    ]);
  });

  it("keeps a genuinely unreachable station labeled Not reachable", () => {
    const stations = new Map([
      ["paris-nord", st("paris-nord", "Paris Gare du Nord")],
      ["berlin", st("berlin", "Berlin Hbf")],
    ]);
    const localReach: ReachFile = {
      origin: "paris-nord", computed_at: "", sample_date: "", destinations: [],
    };
    const cities = buildCityLookup({ Paris: ["paris-nord", "paris-lyon"] });

    expect(destOptions(localReach, stations, "berlin", Infinity, cities)).toMatchObject([
      { station: { id: "berlin" }, group: "Not reachable", disabled: true },
    ]);
  });

  it("keeps an origin outside a city labeled Not reachable", () => {
    const stations = new Map([
      ["utrecht", st("utrecht", "Utrecht Centraal")],
      ["paris-lyon", st("paris-lyon", "Paris Gare de Lyon")],
    ]);
    const localReach: ReachFile = {
      origin: "utrecht", computed_at: "", sample_date: "", destinations: [],
    };
    const cities = buildCityLookup({ Paris: ["paris-nord", "paris-lyon"] });

    expect(destOptions(localReach, stations, "lyon", Infinity, cities)).toMatchObject([
      { station: { id: "paris-lyon" }, group: "Not reachable", disabled: true },
    ]);
  });
});

describe("toFieldOptions", () => {
  it("wraps stations as ungrouped selectable options", () => {
    expect(toFieldOptions([st("x", "X")])).toEqual([
      { kind: "station", station: st("x", "X"), group: "", disabled: false },
    ]);
  });
});

describe("cityOptions", () => {
  it("surfaces matching city origins as all-stations options", () => {
    expect(cityOptions({ Paris: ["paris-nord", "paris-lyon"] }, "par")).toEqual([
      {
        kind: "city",
        city: "Paris",
        memberIds: ["paris-nord", "paris-lyon"],
        label: "Paris — all stations",
        group: "",
        disabled: false,
      },
    ]);
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
