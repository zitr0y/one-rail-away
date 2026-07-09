import { describe, expect, it } from "vitest";
import { pickFeature } from "./pickfeature";

describe("pickFeature", () => {
  it("returns null when nothing was hit", () => {
    expect(pickFeature([])).toBeNull();
  });

  it("picks a destination when a reach-dots feature is hit", () => {
    expect(pickFeature([{ layer: "reach-dots", id: "8100001" }]))
      .toEqual({ type: "dest", id: "8100001" });
  });

  it("picks an origin when only an all-stations feature is hit", () => {
    expect(pickFeature([{ layer: "all-stations", id: "8100002" }]))
      .toEqual({ type: "origin", id: "8100002" });
  });

  it("prefers reach-dots over all-stations when both are hit at the same point", () => {
    expect(pickFeature([
      { layer: "all-stations", id: "8100002" },
      { layer: "reach-dots", id: "8100001" },
    ])).toEqual({ type: "dest", id: "8100001" });
  });

  it("prefers reach-dots over all-stations regardless of hit order", () => {
    expect(pickFeature([
      { layer: "reach-dots", id: "8100001" },
      { layer: "all-stations", id: "8100002" },
    ])).toEqual({ type: "dest", id: "8100001" });
  });

  it("ignores unrelated layers", () => {
    expect(pickFeature([{ layer: "background", id: "x" }])).toBeNull();
  });
});
