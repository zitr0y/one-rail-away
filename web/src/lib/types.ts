export interface Station {
  id: string; name: string; lat: number; lon: number; country: string; has_reach: boolean;
  n_dest?: number; is_capital?: boolean;
}
export interface Leg {
  train: string; dep: string; arr: string; from: string; to: string; via: string[];
}
export interface Journey { trains: number; duration_min: number; legs: Leg[] }
export interface Destination { id: string; direct_per_day: number; journeys: Journey[] }
export interface ReachFile {
  origin: string; computed_at: string; sample_date: string; destinations: Destination[];
}
export interface Meta { computed_at: string; sample_date: string }

export interface CoverageFeature {
  type: "Feature";
  geometry: unknown;
  properties: { tier: "light" | "dark" };
}
export interface CoverageCollection {
  type: "FeatureCollection";
  features: CoverageFeature[];
}
