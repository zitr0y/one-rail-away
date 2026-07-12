import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TripDetails from "./TripDetails";

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
    expect(markup).toContain('/2026-07-13/');
    expect(markup).not.toContain("Pick your time at checkout");
  });

  it("does not render a date input without an eligible journey", () => {
    const markup = renderToStaticMarkup(
      <TripDetails origin={origin} destination={destination} dest={dest}
                   maxTrains={1} stationsById={stationsById} />,
    );
    expect(markup).not.toContain('type="date"');
  });
});
