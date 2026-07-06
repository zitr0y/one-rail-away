"use client";

/**
 * Main page - Train Network Visualization (simplified for pre-computed data)
 */

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import type { StationSummary, PrecomputedConnection } from "@/types";
import { apiClient } from "@/lib/api";
import FilterPanel from "@/components/FilterPanel";

// Dynamically import map component to avoid SSR issues with Leaflet
const TrainNetworkMap = dynamic(() => import("@/components/TrainNetworkMap"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center bg-gray-100">
      <p className="text-gray-600">Loading map...</p>
    </div>
  ),
});

export default function Home() {
  // Available stations (loaded once on mount)
  const [availableStations, setAvailableStations] = useState<StationSummary[]>([]);
  const [isLoadingStations, setIsLoadingStations] = useState(true);

  // Selected station and its connections
  const [selectedStation, setSelectedStation] = useState<StationSummary | null>(null);
  const [connections, setConnections] = useState<PrecomputedConnection[] | null>(null);

  // Client-side filter
  const [minSpeed, setMinSpeed] = useState<number>(0);

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Load available stations on mount
  useEffect(() => {
    const loadStations = async () => {
      try {
        setIsLoadingStations(true);
        const response = await apiClient.getAvailableStations();
        setAvailableStations(response.stations || []);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load available stations"
        );
        console.error("Error loading stations:", err);
      } finally {
        setIsLoadingStations(false);
      }
    };

    loadStations();
  }, []);

  // Load connections when station is selected
  const handleStationSelect = async (station: StationSummary) => {
    setSelectedStation(station);
    setError(null);
    setMinSpeed(0); // Reset filter

    try {
      const response = await apiClient.getStationConnections(station.eva);
      setConnections(response.connections);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load connections"
      );
      setConnections(null);
      console.error("Error loading connections:", err);
    }
  };

  // Handle clicking a station on the map
  const handleMapStationClick = (stationId: string) => {
    // Find the station in available stations
    const station = availableStations.find((s) => s.eva === stationId);
    if (station) {
      handleStationSelect(station);
    } else {
      setError(`Station ${stationId} is not available in pre-computed data`);
    }
  };

  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      <div className="w-96 border-r border-gray-200 flex-shrink-0">
        <FilterPanel
          availableStations={availableStations}
          selectedStation={selectedStation}
          onStationSelect={handleStationSelect}
          isLoadingStations={isLoadingStations}
          connections={connections}
          minSpeed={minSpeed}
          onMinSpeedChange={setMinSpeed}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 relative">
        {error && (
          <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[1000] bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg shadow-lg max-w-md">
            <div className="flex items-start">
              <div className="flex-1">
                <p className="font-bold">Error</p>
                <p className="text-sm">{error}</p>
              </div>
              <button
                onClick={() => setError(null)}
                className="ml-4 text-red-700 hover:text-red-900"
              >
                X
              </button>
            </div>
          </div>
        )}

        {selectedStation && connections ? (
          <TrainNetworkMap
            originStation={selectedStation}
            connections={connections}
            minSpeed={minSpeed}
            onStationClick={handleMapStationClick}
          />
        ) : (
          <div className="h-full w-full flex items-center justify-center bg-gray-100">
            <div className="text-center max-w-md px-4">
              <h1 className="text-3xl font-bold mb-4 text-gray-800">
                Train Network Speed Map
              </h1>
              <p className="text-gray-600 mb-4">
                Visualize train connections and aerial speeds across Germany
              </p>
              <p className="text-sm text-gray-500">
                {isLoadingStations
                  ? "Loading available stations..."
                  : `Select one of ${availableStations.length} stations from the dropdown to begin`}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
