import { describe, expect, it } from "vitest";
import { baseLineOpacity, selectedLineFilter, stationOpacityExpression } from "./highlight";

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
    expect(baseLineOpacity(true)).toBe(0.05);
  });

  it("keeps normal opacity when nothing is selected", () => {
    expect(baseLineOpacity(false)).toBe(0.75);
  });
});

describe("stationOpacityExpression", () => {
  it("returns normal opacity when selectedStationIds is null", () => {
    expect(stationOpacityExpression(null, 0.7)).toBe(0.7);
  });

  it("returns normal opacity when selectedStationIds is empty", () => {
    expect(stationOpacityExpression([], 1.0)).toBe(1.0);
  });

  it("accepts a custom dimmed opacity (reach-view star fade)", () => {
    expect(stationOpacityExpression(["8507000"], 1.0, 0.4)).toEqual([
      "match",
      ["get", "id"],
      ["8507000"],
      1.0,
      0.4,
    ]);
  });

  it("returns a match expression when selectedStationIds is provided", () => {
    expect(stationOpacityExpression(["8507000", "8000001"], 0.7)).toEqual([
      "match",
      ["get", "id"],
      ["8507000", "8000001"],
      0.7,
      0.08,
    ]);
  });
});

