import { describe, expect, it } from "vitest";
import { armedTarget, routeMapClick } from "./mapclick";

describe("armedTarget", () => {
  it("uses the explicitly focused field when set", () => {
    expect(armedTarget("from", true)).toBe("from");
    expect(armedTarget("to", false)).toBe("to");
  });
  it("defaults to 'to' when an origin exists, else 'from'", () => {
    expect(armedTarget(null, true)).toBe("to");
    expect(armedTarget(null, false)).toBe("from");
  });
});

describe("routeMapClick", () => {
  it("From-armed makes any station the origin, even a reachable dot", () => {
    expect(routeMapClick({ type: "dest", id: "x" }, "from")).toEqual({ action: "origin", id: "x" });
    expect(routeMapClick({ type: "origin", id: "y" }, "from")).toEqual({ action: "origin", id: "y" });
  });
  it("To-armed accepts a reachable dot as the destination", () => {
    expect(routeMapClick({ type: "dest", id: "d" }, "to")).toEqual({ action: "dest", id: "d" });
  });
  it("To-armed on an unreachable station yields unreachableTo", () => {
    expect(routeMapClick({ type: "origin", id: "u" }, "to")).toEqual({ action: "unreachableTo", id: "u" });
  });
});
