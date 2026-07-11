import { describe, expect, it } from "vitest";
import { BUCKET_COLORS, BUCKET_LABELS, BRAND } from "./colors";

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
