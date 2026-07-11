import { describe, expect, it } from "vitest";
import { emptyClickAction, swapDest } from "./selection";

describe("emptyClickAction", () => {
  it("clears dest when a destination is selected", () => {
    expect(emptyClickAction(true, true)).toBe("clearDest");
  });

  it("clears all when only an origin is selected", () => {
    expect(emptyClickAction(false, true)).toBe("clearAll");
  });

  it("is a noop when nothing is selected", () => {
    expect(emptyClickAction(false, false)).toBe("noop");
  });
});

describe("swapDest", () => {
  it("returns the old origin id when it is among the new destinations", () => {
    const dests = [{ id: "A" }, { id: "B" }, { id: "C" }];
    expect(swapDest(dests, "B")).toBe("B");
  });

  it("returns null when the old origin is not among the new destinations", () => {
    const dests = [{ id: "A" }, { id: "C" }];
    expect(swapDest(dests, "B")).toBeNull();
  });
});
