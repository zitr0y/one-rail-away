import { describe, expect, it } from "vitest";
import { CORRIDORS, corridorPath } from "./corridors";

const paris = { lon: 2.373481, lat: 48.844945 };
const lyon = { lon: 4.859409, lat: 45.760596 };
const valence = { lon: 4.978652, lat: 44.991907 };
const avignon = { lon: 4.786136, lat: 43.92194 };
const marseille = { lon: 5.380407, lat: 43.302666 };

describe("corridorPath", () => {
  it("routes Paris to Marseille through the LGV corridor waypoints", () => {
    expect(corridorPath(paris, marseille, CORRIDORS)).toEqual([
      paris,
      lyon,
      valence,
      avignon,
      marseille,
    ]);
  });

  it("returns only the endpoints for adjacent corridor waypoints", () => {
    expect(corridorPath(paris, lyon, CORRIDORS)).toEqual([paris, lyon]);
  });

  it("returns null when either endpoint is off the corridor", () => {
    const dijon = { lon: 5.0415, lat: 47.322 };
    expect(corridorPath(paris, dijon, CORRIDORS)).toBeNull();
  });

  it("reverses the corridor path for travel in the opposite direction", () => {
    expect(corridorPath(marseille, paris, CORRIDORS)).toEqual([
      marseille,
      avignon,
      valence,
      lyon,
      paris,
    ]);
  });
});
