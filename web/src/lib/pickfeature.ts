export interface FeatureHit {
  layer: string;
  id: string;
}

export type FeaturePick =
  | { type: "dest"; id: string }
  | { type: "origin"; id: string };

/**
 * Decide which selection a map click represents when multiple layers can be
 * hit at the same point (a reach-dots destination often sits directly on top
 * of a grey all-stations dot). reach-dots always takes precedence.
 */
export function pickFeature(hits: FeatureHit[]): FeaturePick | null {
  const dest = hits.find((h) => h.layer === "reach-dots");
  if (dest) return { type: "dest", id: dest.id };
  const capital = hits.find((h) => h.layer === "capital-stars");
  if (capital) return { type: "origin", id: capital.id };
  const origin = hits.find((h) => h.layer === "all-stations");
  if (origin) return { type: "origin", id: origin.id };
  return null;
}
