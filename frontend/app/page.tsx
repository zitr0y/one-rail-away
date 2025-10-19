"use client";

/**
 * Main page - Train Network Visualization
 */

import { useState } from "react";
import dynamic from "next/dynamic";
import type { NetworkData } from "@/types";
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
  const [networkData, setNetworkData] = useState<NetworkData | null>(null);
  const [minSpeed, setMinSpeed] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [maxChangeovers, setMaxChangeovers] = useState<number>(0);
  const [minTransferTime, setMinTransferTime] = useState<number>(5);
  const [selectedStationName, setSelectedStationName] = useState<string>("Essen Hbf");

  const fetchNetworkData = async (
    stationName: string = selectedStationName,
    forceRefresh: boolean = false
  ) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.fetchNetwork(
        stationName,
        forceRefresh,
        maxChangeovers,
        minTransferTime,
        3 // max routes per destination
      );

      if (response.success && response.data) {
        setNetworkData(response.data);
        setSelectedStationName(response.data.origin_station.name);
        setMinSpeed(0); // Reset filter
      } else {
        setError(response.message || "Failed to fetch network data");
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An unexpected error occurred"
      );
      console.error("Error fetching network data:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStationSelectAndFetch = (stationName: string) => {
    setSelectedStationName(stationName);
    fetchNetworkData(stationName, false);
  };

  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      <div className="w-96 border-r border-gray-200 flex-shrink-0">
        <FilterPanel
          networkData={networkData}
          minSpeed={minSpeed}
          onMinSpeedChange={setMinSpeed}
          maxChangeovers={maxChangeovers}
          onMaxChangeoversChange={setMaxChangeovers}
          minTransferTime={minTransferTime}
          onMinTransferTimeChange={setMinTransferTime}
          selectedStationName={selectedStationName}
          onStationSelectAndFetch={handleStationSelectAndFetch}
          onRefresh={() => fetchNetworkData(selectedStationName, false)}
          isLoading={isLoading}
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
                ✕
              </button>
            </div>
          </div>
        )}

        {networkData ? (
          <TrainNetworkMap
            networkData={networkData}
            minSpeed={minSpeed}
            onStationClick={handleStationSelectAndFetch}
          />
        ) : (
          <div className="h-full w-full flex items-center justify-center bg-gray-100">
            <div className="text-center">
              <h1 className="text-3xl font-bold mb-4 text-gray-800">
                Train Network Speed Map
              </h1>
              <p className="text-gray-600 mb-8">
                Visualize train connections and aerial speeds across Germany
              </p>
              <button
                onClick={() => fetchNetworkData()}
                disabled={isLoading}
                className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 font-medium"
              >
                {isLoading ? "Loading..." : "Load Essen Hbf Network"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
