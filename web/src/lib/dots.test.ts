import { describe, expect, it } from "vitest";

// Mock canvas and document for headless node environment
class MockHTMLCanvasElement {}
if (typeof globalThis.HTMLCanvasElement === "undefined") {
  globalThis.HTMLCanvasElement = MockHTMLCanvasElement as any;
}
if (typeof globalThis.document === "undefined") {
  const mockContext = {
    beginPath: () => {},
    moveTo: () => {},
    lineTo: () => {},
    closePath: () => {},
    fill: () => {},
    stroke: () => {},
  } as unknown as CanvasRenderingContext2D;

  const mockCanvas = Object.create(MockHTMLCanvasElement.prototype);
  Object.assign(mockCanvas, {
    getContext: () => mockContext,
    width: 0,
    height: 0,
  });

  globalThis.document = {
    createElement: (tag: string) => {
      if (tag === "canvas") {
        return mockCanvas;
      }
      return {};
    },
  } as unknown as Document;
}

import { dotRadiusExpression, drawStarIcon } from "./dots";

describe("dotRadiusExpression", () => {
  it("returns a MapLibre expression array", () => {
    const expr = dotRadiusExpression();
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("interpolate");
  });

  it("sizes by n_routes, small at 0, capped at 8", () => {
    const expr = dotRadiusExpression();
    expect(JSON.stringify(expr)).toContain('"n_routes"');
    // Expression structure: ["interpolate", ["linear"], input, ...stop pairs]
    const stops = expr.slice(3); // after interpolation type + input
    expect(stops[0]).toBe(0);
    expect(stops[1]).toBe(2); // most dots stay small (p50 n_routes = 3)
    expect(stops[stops.length - 1]).toBe(8);
  });
});

describe("drawStarIcon", () => {
  // map.addImage accepts {width, height, data} but NOT a raw canvas element —
  // passing a canvas throws at runtime and aborts the whole map load handler.
  it("returns addImage-compatible {width, height, data} of the requested size", () => {
    const img = drawStarIcon(30);
    expect(img.width).toBe(30);
    expect(img.height).toBe(30);
    expect(img.data).toBeInstanceOf(Uint8ClampedArray);
    expect(img.data.length).toBe(30 * 30 * 4);
  });

  it("paints a grey star center and transparent corners", () => {
    const img = drawStarIcon(30);
    const at = (x: number, y: number) => (y * 30 + x) * 4;
    expect(img.data[at(15, 15) + 3]).toBe(255); // center opaque
    expect(img.data[at(15, 15)]).toBe(75); // dark grey fill
    expect(img.data[at(0, 0) + 3]).toBe(0); // corner transparent
    expect(img.data[at(29, 29) + 3]).toBe(0);
  });
});
