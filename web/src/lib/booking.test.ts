import { describe, expect, it } from "vitest";
import { bookingUrl, localDate } from "./booking";

const frankfurt = { id: "8000105", name: "Frankfurt (Main) Hbf", lat: 50.1, lon: 8.66, country: "DE", has_reach: true };
const paris = { id: "8700011", name: "Paris Est", lat: 48.87, lon: 2.35, country: "FR", has_reach: true };

describe("bookingUrl", () => {
  it("builds Trainline's documented search path with origin, destination, tomorrow's date", () => {
    const url = new URL(bookingUrl(frankfurt, paris, "2026-08-20", ""));
    expect(url.hostname).toBe("www.trainline.eu");
    expect(url.pathname).toMatch(
      /^\/search\/Frankfurt%20\(Main\)%20Hbf\/Paris%20Est\/2026-08-20\/$/,
    );
    expect(url.search).toBe("");
  });

  it("appends the affiliate ref when configured", () => {
    const url = new URL(bookingUrl(frankfurt, paris, "2026-08-20", "OSE123"));
    expect(url.searchParams.get("aff")).toBe("OSE123");
  });

  it("formats local calendar dates without a UTC rollover", () => {
    const now = new Date(2026, 6, 12, 23, 30);
    expect(localDate(0, now)).toBe("2026-07-12");
    expect(localDate(1, now)).toBe("2026-07-13");
  });
});
