import { describe, expect, it } from "vitest";
import { buildCityLookup, cityForStation } from "./cities";

describe("buildCityLookup", () => {
  it("builds city-to-members and station-to-city maps once", () => {
    const cities = buildCityLookup({
      Paris: ["paris-nord", "paris-lyon"],
      Bruxelles: ["brussels-midi", "brussels-nord"],
    });

    expect(cities.memberIds("Paris")).toEqual(["paris-nord", "paris-lyon"]);
    expect(cities.cityForStation("brussels-nord")).toBe("Bruxelles");
    expect(cities.cityForStation("outside")).toBeUndefined();
    expect(cities.memberIds("Outside")).toEqual([]);
  });
});

describe("cityForStation", () => {
  const groups = {
    Paris: ["paris-nord", "paris-lyon"],
    Utrecht: ["utrecht"],
    Empty: [],
  };

  it("returns the city and original members for a grouped station", () => {
    expect(cityForStation("paris-lyon", groups)).toEqual({
      city: "Paris", memberIds: groups.Paris,
    });
  });

  it("returns null for stations outside all groups", () => {
    expect(cityForStation("outside", groups)).toBeNull();
  });

  it("excludes singleton and empty groups", () => {
    expect(cityForStation("utrecht", groups)).toBeNull();
    expect(cityForStation("empty", groups)).toBeNull();
  });

  it("returns the first Object.entries match for malformed duplicate members", () => {
    expect(cityForStation("shared", {
      First: ["shared", "first"],
      Second: ["shared", "second"],
    })).toEqual({ city: "First", memberIds: ["shared", "first"] });
  });
});
