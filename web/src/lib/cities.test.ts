import { describe, expect, it } from "vitest";
import { buildCityLookup } from "./cities";

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
