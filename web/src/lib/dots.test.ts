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

import { dotRadiusExpression, clusterRadiusExpression, sortForClusterList, drawStarIcon } from "./dots";

describe("dotRadiusExpression", () => {
  it("returns a MapLibre expression array", () => {
    const expr = dotRadiusExpression();
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("interpolate");
  });

  it("maps n_dest 0 to radius 2.5", () => {
    const expr = dotRadiusExpression();
    // Expression structure: ["interpolate", ["linear"], input, 0, 2.5, sqrt(400), 8]
    const stops = expr.slice(3); // after interpolation type + input
    expect(stops[0]).toBe(0);
    expect(stops[1]).toBe(2.5);
  });

  it("maps n_dest >= 400 to radius 8", () => {
    const expr = dotRadiusExpression();
    const stops = expr.slice(3);
    expect(stops[stops.length - 1]).toBe(8);
  });
});

describe("clusterRadiusExpression", () => {
  it("returns a step expression", () => {
    const expr = clusterRadiusExpression();
    expect(Array.isArray(expr)).toBe(true);
    expect(expr[0]).toBe("step");
  });
});

describe("sortForClusterList", () => {
  it("sorts by n_dest descending", () => {
    const input = [
      { name: "A", n_dest: 10, id: "1" },
      { name: "B", n_dest: 50, id: "2" },
      { name: "C", n_dest: 30, id: "3" },
    ];
    const sorted = sortForClusterList(input);
    expect(sorted.map((s) => s.id)).toEqual(["2", "3", "1"]);
  });

  it("breaks n_dest ties by name ascending", () => {
    const input = [
      { name: "Zürich", n_dest: 100, id: "1" },
      { name: "Bern", n_dest: 100, id: "2" },
    ];
    const sorted = sortForClusterList(input);
    expect(sorted.map((s) => s.id)).toEqual(["2", "1"]);
  });

  it("returns a new array without mutating the input", () => {
    const input = [
      { name: "A", n_dest: 10, id: "1" },
      { name: "B", n_dest: 20, id: "2" },
    ];
    const original = [...input];
    sortForClusterList(input);
    expect(input).toEqual(original);
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
    expect(img.data[at(15, 15)]).toBe(156); // grey fill
    expect(img.data[at(0, 0) + 3]).toBe(0); // corner transparent
    expect(img.data[at(29, 29) + 3]).toBe(0);
  });
});
