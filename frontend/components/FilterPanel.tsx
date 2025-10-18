"use client";

/**
 * Filter and statistics panel component
 */

import { useState } from "react";
import type { NetworkData } from "@/types";
import { formatSpeed, formatDistance } from "@/lib/utils";

interface FilterPanelProps {
  networkData: NetworkData | null;
  minSpeed: number;
  onMinSpeedChange: (speed: number) => void;
  onRefresh: () => void;
  isLoading: boolean;
}

export default function FilterPanel({
  networkData,
  minSpeed,
  onMinSpeedChange,
  onRefresh,
  isLoading,
}: FilterPanelProps) {
  const [stationName, setStationName] = useState("Essen Hbf");

  const handleRefresh = () => {
    onRefresh();
  };

  if (!networkData) {
    return (
      <div className="h-full bg-gray-50 p-6 overflow-y-auto">
        <h2 className="text-2xl font-bold mb-6">Train Network Explorer</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Station Name
            </label>
            <input
              type="text"
              value={stationName}
              onChange={(e) => setStationName(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg"
              placeholder="e.g., Essen Hbf"
            />
          </div>

          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {isLoading ? "Loading..." : "Fetch Network Data"}
          </button>

          {isLoading && (
            <div className="text-center text-sm text-gray-600">
              Fetching data from Deutsche Bahn API...
              <br />
              This may take a minute.
            </div>
          )}
        </div>
      </div>
    );
  }

  const filteredCount = networkData.connections.filter(
    (c) => c.aerial_speed_kmh >= minSpeed
  ).length;

  return (
    <div className="h-full bg-gray-50 p-6 overflow-y-auto">
      <h2 className="text-2xl font-bold mb-2">Train Network Explorer</h2>
      <p className="text-sm text-gray-600 mb-6">
        From {networkData.origin_station.name}
      </p>

      {/* Statistics */}
      <div className="bg-white rounded-lg p-4 mb-6 shadow">
        <h3 className="font-bold mb-3">Statistics</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Total Connections:</span>
            <span className="font-semibold">
              {networkData.total_connections}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Filtered Connections:</span>
            <span className="font-semibold">{filteredCount}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Average Speed:</span>
            <span className="font-semibold">
              {formatSpeed(networkData.average_speed_kmh)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Max Speed:</span>
            <span className="font-semibold">
              {formatSpeed(networkData.max_speed_kmh)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Max Distance:</span>
            <span className="font-semibold">
              {formatDistance(networkData.max_distance_km)}
            </span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg p-4 mb-6 shadow">
        <h3 className="font-bold mb-3">Filters</h3>

        <div className="space-y-4">
          {/* Direct connections toggle */}
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">Direct Connections Only</label>
            <div className="flex items-center">
              <input
                type="checkbox"
                checked={true}
                disabled
                className="h-4 w-4 text-blue-600 rounded"
              />
              <span className="ml-2 text-xs text-gray-500">(Active)</span>
            </div>
          </div>

          {/* Minimum speed slider */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Minimum Aerial Speed: {formatSpeed(minSpeed)}
            </label>
            <input
              type="range"
              min="0"
              max={Math.ceil(networkData.max_speed_kmh)}
              step="10"
              value={minSpeed}
              onChange={(e) => onMinSpeedChange(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0 km/h</span>
              <span>{Math.ceil(networkData.max_speed_kmh)} km/h</span>
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="space-y-3">
        <button
          onClick={handleRefresh}
          disabled={isLoading}
          className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
        >
          {isLoading ? "Loading..." : "Refresh Data"}
        </button>

        <div className="text-xs text-gray-500 text-center">
          Data cached at:{" "}
          {new Date(networkData.timestamp).toLocaleString()}
        </div>
      </div>

      {/* Info */}
      <div className="mt-6 p-4 bg-blue-50 rounded-lg text-sm">
        <h4 className="font-semibold mb-2">About Aerial Speed</h4>
        <p className="text-gray-700">
          Aerial speed is calculated as the straight-line distance between
          stations divided by travel time. It represents how efficiently a
          connection covers geographic distance.
        </p>
      </div>
    </div>
  );
}
