// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { buildOverlapPopupContent } from "./Map";
import type { ReachFile } from "../lib/types";
import type { StationChoice } from "../lib/overlap";

const cityGroups = {
  "Berlin": ["berlin-hbf", "berlin-gesundbrunnen", "berlin-ostbahnhof"],
  "Paris": ["paris-nord", "paris-est"],
};

const choices: StationChoice[] = [
  { pick: { type: "dest", id: "paris-nord" }, name: "Paris Nord", nDest: 100 },
  { pick: { type: "dest", id: "berlin-hbf" }, name: "Berlin Hbf", nDest: 200 },
  { pick: { type: "dest", id: "paris-est" }, name: "Paris Est", nDest: 50 },
];

const mockReach: ReachFile = {
  origin: "berlin-hbf",
  computed_at: "",
  sample_date: "",
  destinations: [
    {
      id: "paris-nord",
      direct_per_day: 1,
      journeys: [
        { trains: 2, duration_min: 500, legs: [] },
      ],
    },
    {
      id: "paris-est",
      direct_per_day: 1,
      journeys: [
        { trains: 1, duration_min: 400, legs: [] },
      ],
    },
  ],
};

describe("buildOverlapPopupContent", () => {
  it("origin chooser has city entry ('(all stations)') and remains sorted by connection count, then name", () => {
    const onSelectCityOrigin = vi.fn();
    const onStationClick = vi.fn();
    const closePopup = vi.fn();

    const dom = buildOverlapPopupContent(
      choices,
      "from",
      cityGroups,
      null, // reach is null on origin selection
      2,
      999,
      onSelectCityOrigin,
      onStationClick,
      closePopup
    );

    const buttons = Array.from(dom.querySelectorAll("button"));
    const textContents = buttons.map(b => b.textContent);

    // Should include the city all stations entries sorted alphabetically (Berlin, Paris)
    expect(textContents).toContain("Berlin (all stations)");
    expect(textContents).toContain("Paris (all stations)");

    // Station list should be sorted by connection count (nDest) desc, then name.
    // Berlin Hbf (200) -> Paris Nord (100) -> Paris Est (50)
    // Station list should match the input order (since origin chooser doesn't sort)
    const stationButtons = buttons.filter(b => !b.classList.contains("overlap-station-popup-city"));
    const stationNames = stationButtons.map(b => b.childNodes[0].textContent?.trim());
    expect(stationNames).toEqual(["Paris Nord", "Berlin Hbf", "Paris Est"]);

    // Clicking city entry works
    const parisCityBtn = buttons.find(b => b.textContent === "Paris (all stations)");
    parisCityBtn?.click();
    expect(onSelectCityOrigin).toHaveBeenCalledWith("Paris", ["paris-nord", "paris-est"]);
    expect(closePopup).toHaveBeenCalled();
  });

  it("target chooser has no city entry ('(all stations)') and is sorted by raw trains-to-reach from origin, then connection count", () => {
    const onSelectCityOrigin = vi.fn();
    const onStationClick = vi.fn();
    const closePopup = vi.fn();

    const dom = buildOverlapPopupContent(
      choices,
      "to",
      cityGroups,
      mockReach,
      2,
      999,
      onSelectCityOrigin,
      onStationClick,
      closePopup
    );

    const buttons = Array.from(dom.querySelectorAll("button"));
    const textContents = buttons.map(b => b.textContent);

    // No city entries
    expect(textContents).not.toContain("Berlin (all stations)");
    expect(textContents).not.toContain("Paris (all stations)");

    // Target sorting:
    // 1. paris-est (raw min trains = 1, nDest = 50)
    // 2. paris-nord (raw min trains = 2, nDest = 100)
    // 3. berlin-hbf (absent from reach destinations, sorts last, nDest = 200)
    const stationNames = buttons.map(b => b.childNodes[0].textContent?.trim());
    expect(stationNames).toEqual(["Paris Est", "Paris Nord", "Berlin Hbf"]);

    // berlin-hbf should have the unreachable hint in target mode under current filters
    const berlinBtn = buttons.find(b => b.childNodes[0].textContent?.trim() === "Berlin Hbf");
    expect(berlinBtn?.classList.contains("unreachable")).toBe(true);
    expect(berlinBtn?.textContent).toContain("not reachable");
  });

  it("target chooser sorted by raw trains-to-reach even when unreachable under current filters, and absent sorts last", () => {
    // Let's set maxTrains to 1.
    // paris-nord requires 2 trains, so it is unreachable under current filters.
    // paris-est requires 1 train, so it is reachable.
    // berlin-hbf is absent from reach.
    const dom = buildOverlapPopupContent(
      choices,
      "to",
      cityGroups,
      mockReach,
      1, // maxTrains = 1
      999,
      vi.fn(),
      vi.fn(),
      vi.fn()
    );

    const buttons = Array.from(dom.querySelectorAll("button"));

    // Sorted by raw trains-to-reach:
    // Paris Est (raw trains = 1) -> Paris Nord (raw trains = 2, but unreachable under filters) -> Berlin Hbf (absent)
    const stationNames = buttons.map(b => b.childNodes[0].textContent?.trim());
    expect(stationNames[0]).toBe("Paris Est");
    expect(stationNames[1]).toBe("Paris Nord");
    expect(stationNames[2]).toBe("Berlin Hbf");

    const parisNordBtn = buttons.find(b => b.childNodes[0].textContent?.trim() === "Paris Nord");
    expect(parisNordBtn?.classList.contains("unreachable")).toBe(true); // filtered out by maxTrains=1
    expect(parisNordBtn?.textContent).toContain("not reachable");

    const berlinBtn = buttons.find(b => b.childNodes[0].textContent?.trim() === "Berlin Hbf");
    expect(berlinBtn?.classList.contains("unreachable")).toBe(true); // absent from reach
  });
});
