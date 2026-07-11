import { describe, expect, it } from "vitest";
import { baseLineOpacity, selectedLineFilter } from "./highlight";

describe("selectedLineFilter", () => {
  it("matches the line feature with the selected destination id", () => {
    expect(selectedLineFilter("8507000")).toEqual(["==", ["get", "id"], "8507000"]);
  });

  it("matches nothing when no journey is selected", () => {
    expect(selectedLineFilter(null)).toEqual(["==", ["get", "id"], ""]);
  });
});

describe("baseLineOpacity", () => {
  it("dims the other lines strongly while a journey is selected", () => {
    expect(baseLineOpacity(true)).toBe(0.04);
  });

  it("keeps normal opacity when nothing is selected", () => {
    expect(baseLineOpacity(false)).toBe(0.75);
  });
});
