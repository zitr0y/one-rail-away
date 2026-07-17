// @vitest-environment jsdom
import { renderToStaticMarkup } from "react-dom/server";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TripDetails from "./TripDetails";
import { frequencyLabel, transferModeIcon } from "./TripDetails";
import type { Destination, TransferMode } from "../lib/types";

const origin = { id: "A", name: "Amsterdam Centraal", lat: 52.4, lon: 4.9, country: "NL", has_reach: true };
const destination = { id: "B", name: "Paris Nord", lat: 48.9, lon: 2.4, country: "FR", has_reach: true };
const dest = {
  id: "B", direct_per_day: 2,
  journeys: [{ trains: 2, duration_min: 240, legs: [
    { train: "ICE 1", dep: "08:00", arr: "10:00", from: "A", to: "B", via: [] },
  ] }],
};
const stationsById = new Map([[origin.id, origin], [destination.id, destination]]);

describe("TripDetails booking date", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-12T12:00:00"));
  });

  afterEach(() => vi.useRealTimers());

  it("renders a friendly date selector and booking URL for an eligible journey", () => {
    const markup = renderToStaticMarkup(
      <TripDetails origin={origin} destination={destination} dest={dest}
                   maxTrains={2} stationsById={stationsById} />,
    );
    expect(markup).toContain('aria-label="Previous day"');
    expect(markup).toContain(">Tomorrow</button>");
    expect(markup).toContain('aria-label="Next day"');
    expect(markup).toContain('type="date"');
    expect(markup).toContain('value="2026-07-13"');
    expect(markup).toContain('min="2026-07-12"');
    expect(markup).toContain('href="https://www.thetrainline.com/"');
    expect(markup).toContain(">Search on Trainline</a>");
    expect(markup).not.toContain("Pick your time at checkout");
  });

  it("does not render a date input without an eligible journey", () => {
    const markup = renderToStaticMarkup(
      <TripDetails origin={origin} destination={destination} dest={dest}
                   maxTrains={1} stationsById={stationsById} />,
    );
    expect(markup).not.toContain('type="date"');
  });

  it("renders an explicit transfer line with icon and approximate minutes", () => {
    const transferStationsById = new Map([
      ...stationsById,
      ["south", { ...origin, id: "south", name: "South Terminal" }],
      ["north", { ...destination, id: "north", name: "North Terminal" }],
    ]);
    const transferDest: Destination = {
      ...dest,
      journeys: [{ trains: 2, duration_min: 240, legs: [
        { train: "ICE 1", dep: "08:00", arr: "10:00", from: "A", to: "south", via: [] },
        { type: "transfer", mode: "metro", minutes: 20, from_id: "south", to_id: "north" },
        { train: "TGV 2", dep: "10:20", arr: "12:00", from: "north", to: "B", via: [] },
      ] }],
    };
    const markup = renderToStaticMarkup(
      <TripDetails origin={origin} destination={destination} dest={transferDest}
                   maxTrains={2} stationsById={transferStationsById} />,
    );
    expect(markup).toContain("~20 min metro to North Terminal");
    expect(markup).toContain('aria-hidden="true">🚇</span>');
    expect(markup).toContain("ICE 1");
    expect(markup).toContain("TGV 2");
    expect(markup).toContain('class="transfer-leg"');
    expect(markup).not.toContain("undefined");
  });

  it("provides an icon for every configured transfer mode", () => {
    const modes: TransferMode[] = [
      "walk", "metro", "tram", "cercanias", "rer", "train-shuttle", "bus",
    ];
    for (const mode of modes) {
      expect(transferModeIcon(mode)).not.toBe("");
    }
  });
});

describe("frequencyLabel", () => {
  it("says when a limited service is present in the selected week", () => {
    expect(frequencyLabel({ ...dest, frequency: {
      sample_days: 8, available_days: 3, direct_days: 3, direct_trips: 3,
      weekly_direct_estimate: 3, availability: "limited", active_months: [],
    } })).toBe("about 3 direct trains per week · limited service · found on 3/8 selected dates");
  });

  it("says when a limited service is absent from the selected week", () => {
    expect(frequencyLabel({ ...dest, frequency: {
      sample_days: 8, available_days: 0, direct_days: 0, direct_trips: 0,
      weekly_direct_estimate: 0, availability: "limited", active_months: [],
    } })).toBe("not running in the selected service week");
  });

  it("never mentions seasonality, even for a stale reach file's retired availability value", () => {
    const label = frequencyLabel({ ...dest, frequency: {
      sample_days: 8, available_days: 3, direct_days: 3, direct_trips: 3,
      weekly_direct_estimate: 3, active_months: [],
      // @ts-expect-error -- old files carry the retired "seasonal_or_limited" value
      availability: "seasonal_or_limited",
    } });
    expect(label.toLowerCase()).not.toContain("seasonal");
  });
});

describe("TripDetails frequency histogram", () => {
  it("renders feed-local histogram hours in the three exact dayparts", () => {
    const histogramDest: Destination = {
      ...dest,
      histogram: {
        "2026-07-14": [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 2, 0, 0, 0, 0, 3, 2, 0, 0, 0, 0, 4],
        "2026-07-15": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 2],
      },
    };
    const markup = renderToStaticMarkup(
      <TripDetails origin={origin} destination={destination} dest={histogramDest}
                   maxTrains={2} stationsById={stationsById} />,
    );
    expect(markup).toContain('aria-label="Tue morning: 4 direct trains"');
    expect(markup).toContain('aria-label="Tue afternoon: 5 direct trains"');
    expect(markup).toContain('aria-label="Tue evening: 6 direct trains"');
    expect(markup).toContain('aria-label="Wed morning: 0 direct trains"');
    expect(markup).toContain('aria-label="Wed afternoon: 2 direct trains"');
    expect(markup).toContain('aria-label="Wed evening: 2 direct trains"');
    expect(markup.indexOf(">Tue<")).toBeLessThan(markup.indexOf(">Wed<"));
    expect(markup).toContain("Sampled timetable evidence");
    expect(markup).toContain("not a promise");
  });

  it("assigns zero-to-four heat levels relative to the busiest daypart", () => {
    const histogramDest: Destination = {
      ...dest,
      histogram: {
        "2026-07-14": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0],
        "2026-07-15": [4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
      },
    };
    const markup = renderToStaticMarkup(
      <TripDetails origin={origin} destination={destination} dest={histogramDest}
                   maxTrains={2} stationsById={stationsById} />,
    );
    expect(markup).toContain("frequency-heat-level-0");
    expect(markup).toContain("frequency-heat-level-1");
    expect(markup).toContain("frequency-heat-level-2");
    expect(markup).toContain("frequency-heat-level-4");
    expect(markup).not.toContain("background:");
  });

  it("clicking the heat strip toggles the existing connection list", () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    const histogramDest: Destination = {
      ...dest,
      histogram: { "2026-07-14": Array.from({ length: 24 }, (_, hour) => hour === 8 ? 1 : 0) },
    };
    act(() => {
      root.render(<TripDetails origin={origin} destination={destination} dest={histogramDest}
                               maxTrains={2} stationsById={stationsById} />);
    });
    const strip = container.querySelector<HTMLButtonElement>(".frequency-heat-strip")!;
    const legs = container.querySelector<HTMLOListElement>(".legs")!;
    expect(strip.getAttribute("aria-expanded")).toBe("false");
    expect(strip.getAttribute("aria-controls")).toBe(legs.id);
    expect(legs.hidden).toBe(true);
    act(() => strip.click());
    expect(strip.getAttribute("aria-expanded")).toBe("true");
    expect(legs.hidden).toBe(false);
    expect(legs.textContent).toContain("ICE 1");
    act(() => strip.click());
    expect(legs.hidden).toBe(true);
    act(() => root.unmount());
  });

  it("falls back to current frequency text and expanded connections without a histogram", () => {
    const frequencyDest: Destination = {
      ...dest,
      frequency: {
        sample_days: 8, available_days: 3, direct_days: 3, direct_trips: 3,
        weekly_direct_estimate: 3, availability: "limited", active_months: [],
      },
    };
    const markup = renderToStaticMarkup(
      <TripDetails origin={origin} destination={destination} dest={frequencyDest}
                   maxTrains={2} stationsById={stationsById} />,
    );
    expect(markup).not.toContain("frequency-heat-strip");
    expect(markup).toContain(frequencyLabel(frequencyDest));
    expect(markup).toContain('class="legs"');
    expect(markup).not.toContain('class="legs" hidden=""');
  });
});
