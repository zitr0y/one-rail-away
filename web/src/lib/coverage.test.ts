import { describe, expect, it } from "vitest";
import { VEIL_TOOLTIP, showVeilTooltip } from "./coverage";

describe("VEIL_TOOLTIP", () => {
  it("is the exact approved copy", () => {
    expect(VEIL_TOOLTIP).toBe(
      "May be reachable by international trains from other countries, but we don't yet have data from this country's rail providers.",
    );
  });
});

describe("showVeilTooltip", () => {
  it("shows when nothing selectable is under the cursor", () => {
    expect(showVeilTooltip(0)).toBe(true);
  });

  it("hides when a station or dot is under the cursor", () => {
    expect(showVeilTooltip(1)).toBe(false);
    expect(showVeilTooltip(3)).toBe(false);
  });
});
