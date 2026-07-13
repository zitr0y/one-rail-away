import { describe, expect, it } from "vitest";
import { unionReach } from "./cityunion";
import type { ReachFile } from "./types";

const reach = (origin: string, destinations: ReachFile["destinations"]): ReachFile => ({
  origin, computed_at: "2026-07-13", sample_date: "2026-07-14", destinations,
});
const journey = (trains: number, duration_min: number) => ({ trains, duration_min, legs: [] });

describe("unionReach", () => {
  it("keeps the overlapping destination with fewer trains, then shorter duration", () => {
    const result = unionReach([
      reach("paris-nord", [{ id: "amsterdam", direct_per_day: 2, journeys: [journey(2, 210)] }]),
      reach("paris-lyon", [{ id: "amsterdam", direct_per_day: 5, journeys: [journey(1, 240)] }]),
      reach("paris-est", [{ id: "amsterdam", direct_per_day: 8, journeys: [journey(1, 220)] }]),
    ]);

    expect(result.destinations).toEqual([
      { id: "amsterdam", direct_per_day: 8, journeys: [journey(1, 220)] },
    ]);
  });

  it("includes every disjoint destination", () => {
    const result = unionReach([
      reach("paris-nord", [{ id: "london", direct_per_day: 3, journeys: [journey(1, 150)] }]),
      reach("paris-lyon", [{ id: "lyon", direct_per_day: 20, journeys: [journey(1, 110)] }]),
    ]);

    expect(result.destinations.map((destination) => destination.id)).toEqual(["london", "lyon"]);
  });

  it("returns an empty reach for no member reaches", () => {
    expect(unionReach([])).toEqual({
      origin: "", computed_at: "", sample_date: "", destinations: [],
    });
  });
});
