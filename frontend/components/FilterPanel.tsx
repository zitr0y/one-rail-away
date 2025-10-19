"use client";

/**
 * Filter and statistics panel component
 */

import type { NetworkData, SearchStationResult } from "@/types";
import { formatSpeed, formatDistance } from "@/lib/utils";
import StationSearch from "./StationSearch";

interface FilterPanelProps {
  networkData: NetworkData | null;
  minSpeed: number;
  onMinSpeedChange: (speed: number) => void;
  maxChangeovers: number;
  onMaxChangeoversChange: (changeovers: number) => void;
  minTransferTime: number;
  onMinTransferTimeChange: (time: number) => void;
  selectedStationName: string;
  onStationSelectAndFetch: (stationName: string) => void;
  onRefresh: () => void;
  isLoading: boolean;
}

export default function FilterPanel({
  networkData,
  minSpeed,
  onMinSpeedChange,
  maxChangeovers,
  onMaxChangeoversChange,
  minTransferTime,
  onMinTransferTimeChange,
  selectedStationName,
  onStationSelectAndFetch,
  onRefresh,
  isLoading,
}: FilterPanelProps) {

  const handleRefresh = () => {
    onRefresh();
  };

  const handleStationSearchSelect = (station: SearchStationResult) => {
    onStationSelectAndFetch(station.name);
  };

  if (!networkData) {
    return (
      <div className="h-full bg-gray-50 p-6 overflow-y-auto">
        <h2 className="text-2xl font-bold mb-6">Train Network Explorer</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Search Station (15,000+ available)
            </label>
            <StationSearch
              onStationSelect={handleStationSearchSelect}
              placeholder="Search for a station (e.g., Berlin, München)"
            />
            {selectedStationName && (
              <p className="text-sm text-gray-600 mt-2">
                Selected: <span className="font-medium">{selectedStationName}</span>
              </p>
            )}
          </div>

          {/* Multi-hop settings */}
          <div className="bg-white rounded-lg p-4 space-y-4">
            <h3 className="font-bold text-sm">Multi-Hop Settings</h3>

            <div>
              <label className="block text-sm font-medium mb-2">
                Max Changeovers: {maxChangeovers}
              </label>
              <input
                type="range"
                min="0"
                max="5"
                step="1"
                value={maxChangeovers}
                onChange={(e) => onMaxChangeoversChange(Number(e.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>Direct only</span>
                <span>Up to 5</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Min Transfer Time (minutes)
              </label>
              <input
                type="number"
                min="1"
                max="60"
                value={minTransferTime}
                onChange={(e) => onMinTransferTimeChange(Number(e.target.value))}
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
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
              This may take a minute{maxChangeovers > 0 ? " (multi-hop takes longer)" : ""}.
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
      <p className="text-sm text-gray-600 mb-4">
        From {networkData.origin_station.name}
      </p>

      {/* Station Search */}
      <div className="bg-white rounded-lg p-4 mb-6 shadow">
        <label className="block text-sm font-medium mb-2">
          Change Station
        </label>
        <StationSearch
          onStationSelect={handleStationSearchSelect}
          placeholder="Search for another station..."
        />
      </div>

      {/* Statistics */}
      <div className="bg-white rounded-lg p-4 mb-6 shadow">
        <h3 className="font-bold mb-3">Statistics</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Direct Connections:</span>
            <span className="font-semibold">
              {networkData.total_connections}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Filtered Connections:</span>
            <span className="font-semibold">{filteredCount}</span>
          </div>
          {networkData.total_multi_hop_routes > 0 && (
            <div className="flex justify-between">
              <span className="text-gray-600">Multi-Hop Routes:</span>
              <span className="font-semibold">
                {networkData.total_multi_hop_routes}
              </span>
            </div>
          )}
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
          {/* Multi-hop controls */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Max Changeovers: {maxChangeovers}
              {maxChangeovers === 0 && <span className="text-xs text-gray-500"> (Direct only)</span>}
            </label>
            <input
              type="range"
              min="0"
              max="5"
              step="1"
              value={maxChangeovers}
              onChange={(e) => onMaxChangeoversChange(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>Direct only</span>
              <span>Up to 5</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Min Transfer Time: {minTransferTime} min
            </label>
            <input
              type="number"
              min="1"
              max="60"
              value={minTransferTime}
              onChange={(e) => onMinTransferTimeChange(Number(e.target.value))}
              className="w-full px-3 py-2 border rounded-lg"
            />
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
      <div className="mt-6 space-y-3">
        <div className="p-4 bg-blue-50 rounded-lg text-sm">
          <h4 className="font-semibold mb-2">About Aerial Speed</h4>
          <p className="text-gray-700">
            Aerial speed is calculated as the straight-line distance between
            stations divided by travel time. It represents how efficiently a
            connection covers geographic distance.
          </p>
        </div>

        {maxChangeovers > 0 && (
          <div className="p-4 bg-green-50 rounded-lg text-sm">
            <h4 className="font-semibold mb-2">Multi-Hop Enabled</h4>
            <p className="text-gray-700">
              Finding routes with up to {maxChangeovers} changeover{maxChangeovers > 1 ? 's' : ''}.
              Click &quot;Refresh Data&quot; to apply changes to multi-hop settings.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
