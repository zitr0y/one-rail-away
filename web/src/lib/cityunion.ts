import type { Destination, Journey, ReachFile } from "./types";

function bestJourney(destination: Destination): Journey | undefined {
  return destination.journeys.reduce<Journey | undefined>((best, journey) => {
    if (!best) return journey;
    if (journey.trains !== best.trains) return journey.trains < best.trains ? journey : best;
    return journey.duration_min < best.duration_min ? journey : best;
  }, undefined);
}

function isBetter(candidate: Destination, current: Destination): boolean {
  const candidateJourney = bestJourney(candidate);
  const currentJourney = bestJourney(current);
  if (!candidateJourney) return false;
  if (!currentJourney) return true;
  if (candidateJourney.trains !== currentJourney.trains) {
    return candidateJourney.trains < currentJourney.trains;
  }
  return candidateJourney.duration_min < currentJourney.duration_min;
}

/** Union member reaches, retaining the best route per destination station. */
export function unionReach(reaches: ReachFile[]): ReachFile {
  if (reaches.length === 0) {
    return { origin: "", computed_at: "", sample_date: "", destinations: [] };
  }

  const destinations = new Map<string, Destination>();
  for (const reach of reaches) {
    for (const destination of reach.destinations) {
      const current = destinations.get(destination.id);
      if (!current || isBetter(destination, current)) destinations.set(destination.id, destination);
    }
  }

  return { ...reaches[0], destinations: Array.from(destinations.values()) };
}
