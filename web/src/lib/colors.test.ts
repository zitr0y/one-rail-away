import { describe, expect, it } from "vitest";
import { BUCKET_COLORS, BUCKET_LABELS, BRAND, themeTokens } from "./colors";

describe("BUCKET_COLORS", () => {
  it("has exactly 4 viridis-reversed entries", () => {
    expect(BUCKET_COLORS).toEqual(["#FDE725", "#35B779", "#31688E", "#440154"]);
  });

  it("matches BUCKET_LABELS length", () => {
    expect(BUCKET_COLORS.length).toBe(BUCKET_LABELS.length);
  });
});

describe("BRAND", () => {
  it("exports navy and gold", () => {
    expect(BRAND.navy).toBe("#003399");
    expect(BRAND.gold).toBe("#FFCC00");
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
      transferRing: "#F2EFE9",
    });
  });
  it("dark swaps to deep-night starting values", () => {
    expect(themeTokens("dark")).toEqual({
      stationDot: "#5B7FDB",
      reachDotStroke: "#101C36",
      veil: "#6B7590",
      riderStroke: "#F2EFE9",
      riderHollow: "#101C36",
      transferRing: "#101C36",
    });
  });
});
