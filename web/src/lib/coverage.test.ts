import { describe, expect, it } from "vitest";
import { VEIL_LEGEND, coverageTooltip, showVeilTooltip, veilFilter } from "./coverage";

describe("veilFilter", () => {
  it("matches only non-covered countries", () => {
    expect(veilFilter()).toEqual(["==", ["get", "covered"], false]);
  });
});

describe("coverageTooltip", () => {
  it("formats the not-yet-in-system tooltip", () => {
    expect(coverageTooltip("Italy")).toBe("Italy — not yet in our system");
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

describe("VEIL_LEGEND", () => {
  it("is the exact approved copy", () => {
    expect(VEIL_LEGEND).toBe("Grey countries: not yet in our system");
  });
});
