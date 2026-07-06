/**
 * Utility functions for data visualization
 */

import type { Connection } from "@/types";

/**
 * Get color based on aerial speed (gradient from red to green)
 * @param speed Speed in km/h
 * @param minSpeed Minimum speed in dataset
 * @param maxSpeed Maximum speed in dataset
 * @returns RGB color string
 */
export function getSpeedColor(
  speed: number,
  minSpeed: number = 0,
  maxSpeed: number = 300
): string {
  // Normalize speed to 0-1 range
  const normalized = Math.max(0, Math.min(1, (speed - minSpeed) / (maxSpeed - minSpeed)));

  // Color gradient: red (slow) -> yellow (medium) -> green (fast)
  let r, g, b;

  if (normalized < 0.5) {
    // Red to yellow
    r = 255;
    g = Math.round(normalized * 2 * 255);
    b = 0;
  } else {
    // Yellow to green
    r = Math.round((1 - (normalized - 0.5) * 2) * 255);
    g = 255;
    b = 0;
  }

  return `rgb(${r}, ${g}, ${b})`;
}

/**
 * Get connection frequency weight for line thickness
 * @param connections All connections
 * @param destination Destination station name
 * @returns Weight (1-5)
 */
export function getConnectionWeight(
  connections: Connection[],
  destination: string
): number {
  const count = connections.filter(
    (c) => c.destination_name === destination
  ).length;

  // Map count to weight (1-5)
  if (count === 1) return 2;
  if (count <= 3) return 3;
  if (count <= 10) return 4;
  return 5;
}

/**
 * Format speed for display
 */
export function formatSpeed(speed: number): string {
  return `${speed.toFixed(1)} km/h`;
}

/**
 * Format distance for display
 */
export function formatDistance(distance: number): string {
  return `${distance.toFixed(1)} km`;
}

/**
 * Format duration in minutes to human readable
 */
export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;

  if (hours === 0) {
    return `${mins}m`;
  }

  return `${hours}h ${mins}m`;
}

/**
 * Group connections by destination to get unique destinations
 */
export function getUniqueDestinations(connections: Connection[]): Connection[] {
  const destinationMap = new Map<string, Connection>();

  for (const connection of connections) {
    const key = connection.destination_name;
    // Keep the fastest connection to each destination
    if (
      !destinationMap.has(key) ||
      connection.aerial_speed_kmh > destinationMap.get(key)!.aerial_speed_kmh
    ) {
      destinationMap.set(key, connection);
    }
  }

  return Array.from(destinationMap.values());
}

/**
 * Filter connections based on criteria
 */
export function filterConnections(
  connections: Connection[],
  minSpeed: number | null = null
): Connection[] {
  let filtered = [...connections];

  if (minSpeed !== null) {
    filtered = filtered.filter((c) => c.aerial_speed_kmh >= minSpeed);
  }

  return filtered;
}
