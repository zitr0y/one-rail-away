export type CorridorPoint = { lon: number; lat: number };
export type CorridorWaypoint = CorridorPoint & { name: string };
export type Corridor = { name: string; waypoints: readonly CorridorWaypoint[] };

// Allows nearby station variants to share a trunk while rejecting unrelated cities.
export const CORRIDOR_SNAP_THRESHOLD_KM = 20;

export const CORRIDORS: readonly Corridor[] = [
  {
    name: "Paris–Lyon–Marseille LGV",
    waypoints: [
      { name: "Paris Gare de Lyon", lon: 2.373481, lat: 48.844945 },
      { name: "Lyon Part Dieu", lon: 4.859409, lat: 45.760596 },
      { name: "Valence TGV Rhône-Alpes Sud", lon: 4.978652, lat: 44.991907 },
      { name: "Avignon TGV", lon: 4.786136, lat: 43.92194 },
      { name: "Marseille Saint-Charles", lon: 5.380407, lat: 43.302666 },
    ],
  },
];

function distanceKm(a: CorridorPoint, b: CorridorPoint): number {
  const toRadians = (degrees: number) => degrees * Math.PI / 180;
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);
  const latitudeDelta = lat2 - lat1;
  const longitudeDelta = toRadians(b.lon - a.lon);
  const sinLatitude = Math.sin(latitudeDelta / 2);
  const sinLongitude = Math.sin(longitudeDelta / 2);
  const haversine = sinLatitude ** 2
    + Math.cos(lat1) * Math.cos(lat2) * sinLongitude ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

function nearestWaypointIndex(point: CorridorPoint, corridor: Corridor): number | null {
  let nearestIndex: number | null = null;
  let nearestDistance = CORRIDOR_SNAP_THRESHOLD_KM;
  corridor.waypoints.forEach((waypoint, index) => {
    const distance = distanceKm(point, waypoint);
    if (distance <= nearestDistance) {
      nearestIndex = index;
      nearestDistance = distance;
    }
  });
  return nearestIndex;
}

export function corridorPath(
  from: CorridorPoint,
  to: CorridorPoint,
  corridors: readonly Corridor[],
): CorridorPoint[] | null {
  for (const corridor of corridors) {
    const fromIndex = nearestWaypointIndex(from, corridor);
    const toIndex = nearestWaypointIndex(to, corridor);
    if (fromIndex === null || toIndex === null || fromIndex === toIndex) continue;

    const intermediate = fromIndex < toIndex
      ? corridor.waypoints.slice(fromIndex + 1, toIndex)
      : corridor.waypoints.slice(toIndex + 1, fromIndex).toReversed();
    return [from, ...intermediate.map(({ lon, lat }) => ({ lon, lat })), to];
  }
  return null;
}
