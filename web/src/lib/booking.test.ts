import { describe, expect, it } from "vitest";
import { bookingUrl, friendlyDateLabel, localDate, shiftDate } from "./booking";

describe("bookingUrl", () => {
  it("links to the server-side Trainline redirect with ids and date", () => {
    expect(bookingUrl("x:db_fern:1", "B", "2026-07-13"))
      .toBe("/api/book?from=x%3Adb_fern%3A1&to=B&date=2026-07-13");
  });

  it("formats local calendar dates without a UTC rollover", () => {
    const now = new Date(2026, 6, 12, 23, 30);
    expect(localDate(0, now)).toBe("2026-07-12");
    expect(localDate(1, now)).toBe("2026-07-13");
  });

  it("moves ISO dates by local calendar days", () => {
    expect(shiftDate("2026-07-13", -1)).toBe("2026-07-12");
    expect(shiftDate("2026-07-31", 1)).toBe("2026-08-01");
  });

  it("uses friendly labels around today", () => {
    expect(friendlyDateLabel("2026-07-12", "2026-07-12")).toBe("Today");
    expect(friendlyDateLabel("2026-07-13", "2026-07-12")).toBe("Tomorrow");
    expect(friendlyDateLabel("2026-07-14", "2026-07-12")).toBe("Tue 14 Jul");
  });
});
