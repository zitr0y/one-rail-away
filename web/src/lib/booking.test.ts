import { describe, expect, it } from "vitest";
import { bookingUrl } from "./booking";

const frankfurt = { id: "8000105", name: "Frankfurt (Main) Hbf", lat: 50.1, lon: 8.66, country: "DE", has_reach: true };
const paris = { id: "8700011", name: "Paris Est", lat: 48.87, lon: 2.35, country: "FR", has_reach: true };

describe("bookingUrl", () => {
  it("builds a Trainline deep link with origin, destination, tomorrow's date", () => {
    const url = new URL(bookingUrl(frankfurt, paris, ""));
    expect(url.hostname).toBe("www.thetrainline.com");
    expect(url.searchParams.get("origin")).toBe("Frankfurt (Main) Hbf");
    expect(url.searchParams.get("destination")).toBe("Paris Est");
    expect(url.searchParams.get("outwardDate")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(url.searchParams.has("aff")).toBe(false);
  });

  it("appends the affiliate ref when configured", () => {
    const url = new URL(bookingUrl(frankfurt, paris, "OSE123"));
    expect(url.searchParams.get("aff")).toBe("OSE123");
  });
});
