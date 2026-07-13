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

import {
  dotRadiusExpression,
  reachDotRadiusExpression,
  starSizeExpression,
  stationDotOpacityByZoom,
  allStationOpacityExpression,
  drawStarIcon,
  drawStopSignIcon,
} from "./dots";
import { stationOpacityExpression } from "./highlight";

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
    expect(stops[stops.length - 1]).toBe(9);
  });

  it("sizes reach dots by n_routes with a clickability floor of 4.5", () => {
    const expr = reachDotRadiusExpression();
    expect(JSON.stringify(expr)).toContain('"n_routes"');
    const stops = expr.slice(3);
    expect(stops[0]).toBe(0);
    expect(stops[1]).toBe(4.5); // floor: never smaller than near the old uniform 5.5
    expect(stops[stops.length - 1]).toBe(9);
  });

  it("scales capital stars by n_routes on the same sqrt scale", () => {
    const expr = starSizeExpression();
    expect(JSON.stringify(expr)).toContain('"n_routes"');
    const stops = expr.slice(3);
    expect(stops[1]).toBe(0.55);
    expect(stops[stops.length - 1]).toBe(1.05);
  });
});

describe("stationDotOpacityByZoom", () => {
  it("reveals lower-destination stations at progressively closer zoom levels", () => {
    expect(stationDotOpacityByZoom()).toEqual([
      "interpolate", ["linear"], ["zoom"],
      4, ["step", ["get", "n_dest"], 0, 150, 0.7],
      5.5, ["step", ["get", "n_dest"], 0, 50, 0.7],
      7, ["step", ["get", "n_dest"], 0, 10, 0.7],
      9, 0.7,
    ]);
  });
});

describe("allStationOpacityExpression", () => {
  function zoomIsOnlyTheTopLevelInput(expression: unknown): boolean {
    if (!Array.isArray(expression) || expression[0] !== "interpolate") return false;
    let zoomCount = 0;
    const visit = (value: unknown, isTopLevelInput = false) => {
      if (!Array.isArray(value)) return;
      if (value[0] === "zoom") {
        zoomCount += 1;
        expect(isTopLevelInput).toBe(true);
      }
      value.forEach((child, index) => visit(child, value === expression && index === 2));
    };
    visit(expression);
    return zoomCount === 1;
  }

  it("keeps zoom as the outer interpolate input when pinning reach stations", () => {
    const expression = allStationOpacityExpression(["origin", "journey"], 0.25);
    expect(zoomIsOnlyTheTopLevelInput(expression)).toBe(true);
    expect(expression).toEqual([
      "interpolate", ["linear"], ["zoom"],
      4, ["match", ["get", "id"], ["origin", "journey"], 0.7,
        ["*", ["step", ["get", "n_dest"], 0, 150, 0.7], 0.25]],
      5.5, ["match", ["get", "id"], ["origin", "journey"], 0.7,
        ["*", ["step", ["get", "n_dest"], 0, 50, 0.7], 0.25]],
      7, ["match", ["get", "id"], ["origin", "journey"], 0.7,
        ["*", ["step", ["get", "n_dest"], 0, 10, 0.7], 0.25]],
      9, ["match", ["get", "id"], ["origin", "journey"], 0.7,
        ["*", 0.7, 0.25]],
    ]);
  });

  it("pins origin and journey ids while dimming all other stations", () => {
    const journeyOpacity = stationOpacityExpression(["journey"], 0.7);
    const expression = allStationOpacityExpression(["origin", "journey"], journeyOpacity);
    const closeZoomOutput = expression[10] as unknown[];

    expect(closeZoomOutput.slice(1, 4)).toEqual([["get", "id"], ["origin", "journey"], 0.7]);
    expect(closeZoomOutput[4]).toEqual(["*", 0.7, journeyOpacity]);
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

  it("paints a gold star center and transparent corners", () => {
    const img = drawStarIcon(30);
    const at = (x: number, y: number) => (y * 30 + x) * 4;
    expect(img.data[at(15, 15) + 3]).toBe(255); // center opaque
    expect(img.data[at(15, 15)]).toBe(255); // brand-gold fill (255,204,0)
    expect(img.data[at(15, 15) + 1]).toBe(204);
    expect(img.data[at(0, 0) + 3]).toBe(0); // corner transparent
    expect(img.data[at(29, 29) + 3]).toBe(0);
  });
});

describe("drawStopSignIcon", () => {
  it("returns addImage-compatible {width, height, data} of the requested size", () => {
    const img = drawStopSignIcon(30);
    expect(img.width).toBe(30);
    expect(img.height).toBe(30);
    expect(img.data).toBeInstanceOf(Uint8ClampedArray);
    expect(img.data.length).toBe(30 * 30 * 4);
  });

  it("paints a red field with a white centre stripe and transparent corners", () => {
    const img = drawStopSignIcon(30);
    const at = (x: number, y: number) => (y * 30 + x) * 4;
    // Centre row is the white stripe.
    expect(img.data[at(15, 15) + 3]).toBe(255); // opaque
    expect(img.data[at(15, 15)]).toBe(255); // white stripe
    expect(img.data[at(15, 15) + 1]).toBe(255);
    expect(img.data[at(15, 15) + 2]).toBe(255);
    // Off the stripe, inside the octagon: stop-red.
    expect(img.data[at(15, 8)]).toBe(193); // #C1121F red (193,18,31)
    expect(img.data[at(15, 8) + 1]).toBe(18);
    expect(img.data[at(15, 8) + 2]).toBe(31);
    expect(img.data[at(0, 0) + 3]).toBe(0); // octagon corner transparent
    expect(img.data[at(29, 29) + 3]).toBe(0);
  });
});
