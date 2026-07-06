/**
 * API client for backend communication
 */

import type {
  NetworkData,
  FetchNetworkResponse,
  SearchStationsResponse,
  TrainCategory,
  AvailableStationsResponse,
  PrecomputedConnectionsResponse,
} from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async fetchNetwork(
    stationName: string = "Essen Hbf",
    forceRefresh: boolean = false,
    maxChangeovers: number = 0,
    minTransferTime?: number,
    maxRoutesPerDestination?: number,
    showOnlyHubsAndEndpoints?: boolean,
    deutschlandTicketOnly: boolean = false,
    trainCategories?: TrainCategory[]
  ): Promise<FetchNetworkResponse> {
    const response = await fetch(`${this.baseUrl}/api/fetch-network`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        station_name: stationName,
        force_refresh: forceRefresh,
        max_changeovers: maxChangeovers,
        min_transfer_time: minTransferTime,
        max_routes_per_destination: maxRoutesPerDestination,
        show_only_hubs_and_endpoints: showOnlyHubsAndEndpoints,
        deutschland_ticket_only: deutschlandTicketOnly,
        train_categories: trainCategories,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage = errorData.detail || response.statusText;
      console.error("API Error:", errorData);
      throw new Error(`Failed to fetch network data: ${errorMessage}`);
    }

    return response.json();
  }

  async getNetwork(stationId: string): Promise<NetworkData> {
    const response = await fetch(`${this.baseUrl}/api/network/${stationId}`);

    if (!response.ok) {
      throw new Error(`Failed to get network data: ${response.statusText}`);
    }

    return response.json();
  }

  async getCachedStations(): Promise<{
    total: number;
    stations: Array<{
      station_id: string;
      station_name: string;
      connection_count: number;
      cached_at: string;
    }>;
  }> {
    const response = await fetch(`${this.baseUrl}/api/stations/cached`);

    if (!response.ok) {
      throw new Error(`Failed to get cached stations: ${response.statusText}`);
    }

    return response.json();
  }

  async getTopStations(limit: number = 10): Promise<{
    total: number;
    limit: number;
    stations: Array<{
      station_id: string;
      station_name: string;
      connection_count: number;
    }>;
  }> {
    const response = await fetch(
      `${this.baseUrl}/api/stations/top?limit=${limit}`
    );

    if (!response.ok) {
      throw new Error(`Failed to get top stations: ${response.statusText}`);
    }

    return response.json();
  }

  async searchStations(
    query: string,
    limit: number = 20
  ): Promise<SearchStationsResponse> {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString(),
    });

    const response = await fetch(
      `${this.baseUrl}/api/stations/search?${params}`
    );

    if (!response.ok) {
      throw new Error(`Failed to search stations: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get list of available stations with pre-computed data
   */
  async getAvailableStations(): Promise<AvailableStationsResponse> {
    const response = await fetch(`${this.baseUrl}/api/stations/available`);

    if (!response.ok) {
      throw new Error(`Failed to get available stations: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get pre-computed connections for a specific station
   */
  async getStationConnections(stationId: string): Promise<PrecomputedConnectionsResponse> {
    const response = await fetch(`${this.baseUrl}/api/connections/${stationId}`);

    if (!response.ok) {
      throw new Error(`Failed to get station connections: ${response.statusText}`);
    }

    return response.json();
  }
}

export const apiClient = new APIClient();
