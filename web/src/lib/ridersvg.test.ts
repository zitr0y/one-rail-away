// web/src/lib/ridersvg.test.ts
import { describe, expect, it } from "vitest";
import { riderSvg } from "./ridersvg";

describe("riderSvg", () => {
  const svg = riderSvg("#003399", "#F2EFE9");

  it("bakes in stroke and hollow colors", () => {
    expect(svg).toContain('stroke="#003399"');
    expect(svg).toContain('fill="#F2EFE9"');
  });

  it("keeps the gold star in both themes", () => {
    expect(svg).toContain('fill="#ffcc00"');
    expect(svg).toContain("★");
  });

  it("drops the baked-in route line and station dots", () => {
    expect(svg).not.toContain("M4 80"); // left line segment of the logo
    expect(svg).not.toContain('cx="14"'); // left station dot
    expect(svg).not.toContain('cx="184"'); // right station dot
  });

  it("is vertically centered on the rail (y=80) for center-anchored rotation", () => {
    expect(svg).toContain('viewBox="32 28 132 104"');
  });
});
