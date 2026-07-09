import { describe, expect, it } from "vitest";
import { keyNav } from "./keynav";

describe("keyNav", () => {
  it("passes through when there are no results", () => {
    expect(keyNav("Enter", { index: -1, count: 0 })).toEqual({ type: "pass" });
    expect(keyNav("ArrowDown", { index: -1, count: 0 })).toEqual({ type: "pass" });
  });

  it("moves down and wraps", () => {
    expect(keyNav("ArrowDown", { index: -1, count: 3 })).toEqual({ type: "move", index: 0 });
    expect(keyNav("ArrowDown", { index: 2, count: 3 })).toEqual({ type: "move", index: 0 });
  });

  it("moves up and wraps", () => {
    expect(keyNav("ArrowUp", { index: 0, count: 3 })).toEqual({ type: "move", index: 2 });
    expect(keyNav("ArrowUp", { index: -1, count: 3 })).toEqual({ type: "move", index: 2 });
  });

  it("enter selects the highlighted result, defaulting to the first", () => {
    expect(keyNav("Enter", { index: 1, count: 3 })).toEqual({ type: "select", index: 1 });
    expect(keyNav("Enter", { index: -1, count: 3 })).toEqual({ type: "select", index: 0 });
  });

  it("escape closes", () => {
    expect(keyNav("Escape", { index: 1, count: 3 })).toEqual({ type: "close" });
  });

  it("other keys pass through", () => {
    expect(keyNav("a", { index: 1, count: 3 })).toEqual({ type: "pass" });
  });
});
