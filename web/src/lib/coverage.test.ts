import { describe, expect, it } from "vitest";
import { VEIL_TOOLTIP_LIGHT, VEIL_TOOLTIP_DARK, veilTooltip, showVeilTooltip } from "./coverage";

describe("veilTooltip", () => {
  it("has the exact approved copy for light and dark tiers", () => {
    expect(VEIL_TOOLTIP_LIGHT).toBe(
      "Reachable by international trains, but we don't yet have data from this country's rail providers.",
    );
    expect(VEIL_TOOLTIP_DARK).toBe(
      "We don't yet have train data for this country.",
    );
  });

  it("maps light to light tooltip and other things to dark tooltip", () => {
    expect(veilTooltip("light")).toBe(VEIL_TOOLTIP_LIGHT);
    expect(veilTooltip("dark")).toBe(VEIL_TOOLTIP_DARK);
    expect(veilTooltip(undefined)).toBe(VEIL_TOOLTIP_DARK);
    expect(veilTooltip("other")).toBe(VEIL_TOOLTIP_DARK);
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
