import { describe, expect, it } from "vitest";
import { CORRIDORS, corridorPath } from "./corridors";

const paris = { lon: 2.373481, lat: 48.844945 };
const lyon = { lon: 4.859409, lat: 45.760596 };
const valence = { lon: 4.978652, lat: 44.991907 };
const avignon = { lon: 4.786136, lat: 43.92194 };
const marseille = { lon: 5.380407, lat: 43.302666 };
const parisMontparnasse = { lon: 2.320514, lat: 48.841172 };
const saintPierreDesCorps = { lon: 0.723539, lat: 47.38614 };
const poitiers = { lon: 0.333136, lat: 46.582232 };
const angouleme = { lon: 0.164608, lat: 45.653572 };
const bordeaux = { lon: -0.556697, lat: 44.825873 };

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

  it("routes Paris Montparnasse to Bordeaux through the Atlantic LGV waypoints", () => {
    expect(corridorPath(parisMontparnasse, bordeaux, CORRIDORS)).toEqual([
      parisMontparnasse,
      saintPierreDesCorps,
      poitiers,
      angouleme,
      bordeaux,
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

  it("snaps endpoints within 20km but rejects one just outside the boundary", () => {
    const nearParis = { lon: paris.lon, lat: paris.lat + 0.1 }; // ~11km north
    const outsideParis = { lon: paris.lon, lat: paris.lat + 0.19 }; // ~21km north

    expect(corridorPath(nearParis, marseille, CORRIDORS)).toEqual([
      nearParis,
      lyon,
      valence,
      avignon,
      marseille,
    ]);
    expect(corridorPath(outsideParis, marseille, CORRIDORS)).toBeNull();
  });

  it("returns null when both endpoints snap to the same waypoint", () => {
    const northOfParis = { lon: paris.lon, lat: paris.lat + 0.05 };
    const southOfParis = { lon: paris.lon, lat: paris.lat - 0.05 };

    expect(corridorPath(northOfParis, southOfParis, CORRIDORS)).toBeNull();
  });
});
