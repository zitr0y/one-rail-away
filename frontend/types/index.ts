/**
 * Type definitions for train network data
 */

export interface Station {
  id: string;
  name: string;
  lat: number;
  lon: number;
  connection_count: number;
  neighbor_count: number;
  is_hub: boolean;
  is_endpoint: boolean;
}

export interface RouteWaypoint {
  station_name: string;
  lat: number;
  lon: number;
  arrival_time: string | null;
  distance_from_origin_km: number;
}

export type TrainCategory = "regional" | "intercity" | "other";

export interface Connection {
  origin_id: string;
  origin_name: string;
  destination_id: string;
  destination_name: string;
  destination_lat: number;
  destination_lon: number;
  train_type: string;
  train_number: string | null;
  departure_time: string;
  arrival_time: string;
  travel_time_minutes: number;
  distance_km: number;
  aerial_speed_kmh: number;
  route_waypoints: RouteWaypoint[];
  platform: string | null;
  delay: number | null;
  is_real_time: boolean;
}

export interface ConnectionLeg {
  origin_id: string;
  origin_name: string;
  destination_id: string;
  destination_name: string;
  train_type: string;
  train_number: string | null;
  departure_time: string;
  arrival_time: string;
  travel_time_minutes: number;
  distance_km: number;
  aerial_speed_kmh: number;
  platform: string | null;
}

export interface TransferInfo {
  station_id: string;
  station_name: string;
  station_lat: number;
  station_lon: number;
  arrival_time: string;
  departure_time: string;
  waiting_time_minutes: number;
  arrival_platform: string | null;
  departure_platform: string | null;
}

export interface MultiHopRoute {
  origin_id: string;
  origin_name: string;
  destination_id: string;
  destination_name: string;
  destination_lat: number;
  destination_lon: number;
  legs: ConnectionLeg[];
  transfers: TransferInfo[];
  total_travel_time_minutes: number;
  total_distance_km: number;
  total_waiting_time_minutes: number;
  number_of_changeovers: number;
  average_aerial_speed_kmh: number;
  departure_time: string;
  arrival_time: string;
  is_real_time: boolean;
}

export interface NetworkData {
  timestamp: string;
  origin_station: Station;
  connections: Connection[];
  multi_hop_routes: MultiHopRoute[];
  total_connections: number;
  total_multi_hop_routes: number;
  average_speed_kmh: number;
  max_speed_kmh: number;
  max_distance_km: number;
}

export interface SearchStationResult {
  id: string;
  name: string;
  lat: number;
  lon: number;
}

export interface SearchStationsResponse {
  query: string;
  total_results: number;
  returned_results: number;
  stations: SearchStationResult[];
}

export interface FetchNetworkResponse {
  success: boolean;
  message: string;
  data: NetworkData | null;
  cached: boolean;
}

export interface FilterOptions {
  direct_only: boolean;
  min_speed_kmh: number | null;
  max_speed_kmh: number | null;
  train_types: string[] | null;
}
