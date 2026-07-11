import { describe, expect, it } from "vitest";
import { styleUrl } from "./mapstyle";

describe("styleUrl", () => {
  it("returns the local light style path", () => {
    expect(styleUrl("light")).toBe("/mapstyle-light.json");
  });
});
