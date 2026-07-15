import { describe, expect, it } from "vitest";
import { BUCKET_COLORS, themeTokens } from "./colors";

describe("BUCKET_COLORS", () => {
  it("has exactly 4 viridis-reversed entries", () => {
    expect(BUCKET_COLORS).toEqual(["#FDE725", "#35B779", "#31688E", "#440154"]);
  });
});

describe("themeTokens", () => {
  it("light matches today's calibrated values", () => {
    expect(themeTokens("light")).toEqual({
      stationDot: "#003399",
      reachDotStroke: "#F2EFE9",
      veil: "#9c9589",
      riderStroke: "#003399",
      riderHollow: "#F2EFE9",
    });
  });
  it("dark swaps to deep-night starting values", () => {
    expect(themeTokens("dark")).toEqual({
      stationDot: "#5B7FDB",
      reachDotStroke: "#101C36",
      veil: "#6B7590",
      riderStroke: "#F2EFE9",
      riderHollow: "#101C36",
    });
  });
});
