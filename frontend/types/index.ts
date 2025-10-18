/**
 * Type definitions for train network data
 */

export interface Station {
  id: string;
  name: string;
  lat: number;
  lon: number;
  connection_count: number;
}

export interface RouteWaypoint {
  station_name: string;
  lat: number;
  lon: number;
  arrival_time: string | null;
  distance_from_origin_km: number;
}

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

export interface NetworkData {
  timestamp: string;
  origin_station: Station;
  connections: Connection[];
  total_connections: number;
  average_speed_kmh: number;
  max_speed_kmh: number;
  max_distance_km: number;
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
