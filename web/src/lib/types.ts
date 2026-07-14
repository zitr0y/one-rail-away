export interface Station {
  id: string; name: string; lat: number; lon: number; country: string; has_reach: boolean;
  n_dest?: number; n_routes?: number; is_capital?: boolean;
}
export interface Leg {
  train: string; dep: string; arr: string; from: string; to: string; via: string[];
}
export interface Journey { trains: number; duration_min: number; legs: Leg[] }
export interface Frequency {
  requested_sample_days?: number; sample_days: number; available_days: number; direct_days: number; direct_trips: number;
  direct_per_active_day?: number | null; weekly_direct_estimate?: number | null;
  availability: "year_round" | "seasonal_or_limited" | "coverage_limited"; seasonal?: boolean; active_months: string[];
}
export interface Destination {
  id: string; direct_per_day: number; journeys: Journey[]; frequency?: Frequency | null;
}
export interface ReachFile {
  origin: string; computed_at: string; sample_date: string; destinations: Destination[];
}
export interface Meta { computed_at: string; sample_date: string; sample_dates?: string[] }
export type CityGroups = Record<string, string[]>;

export interface CoverageFeature {
  type: "Feature";
  geometry: unknown;
  properties: { tier: "light" | "dark" };
}
export interface CoverageCollection {
  type: "FeatureCollection";
  features: CoverageFeature[];
}

export interface RailPathsFile {
  attribution: string;
  paths: Record<string, [number, number][]>;
}
