"use client";

/**
 * Filter and statistics panel component (simplified for pre-computed data)
 */

import type { StationSummary, PrecomputedConnection } from "@/types";
import { formatSpeed, formatDistance } from "@/lib/utils";
import StationSelector from "./StationSelector";

interface FilterPanelProps {
  // Station selection
  availableStations: StationSummary[];
  selectedStation: StationSummary | null;
  onStationSelect: (station: StationSummary) => void;
  isLoadingStations: boolean;

  // Connection data
  connections: PrecomputedConnection[] | null;

  // Filters (client-side)
  minSpeed: number;
  onMinSpeedChange: (speed: number) => void;
}

export default function FilterPanel({
  availableStations,
  selectedStation,
  onStationSelect,
  isLoadingStations,
  connections,
  minSpeed,
  onMinSpeedChange,
}: FilterPanelProps) {
  // Calculate statistics from connections
  const stats = connections
    ? {
        totalConnections: connections.length,
        filteredConnections: connections.filter(
          (c) => c.aerial_speed_kmh >= minSpeed
        ).length,
        maxSpeed: Math.max(...connections.map((c) => c.aerial_speed_kmh), 0),
        avgSpeed:
          connections.length > 0
            ? connections.reduce((sum, c) => sum + c.aerial_speed_kmh, 0) /
              connections.length
            : 0,
        maxDistance: Math.max(...connections.map((c) => c.distance_km), 0),
      }
    : null;

  // No data state - show station selector prominently
  if (!connections) {
    return (
      <div className="h-full bg-gray-50 p-6 overflow-y-auto">
        <h2 className="text-2xl font-bold mb-6">Train Network Explorer</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Select Station ({availableStations.length} available)
            </label>
            <StationSelector
              stations={availableStations}
              selectedStation={selectedStation}
              onSelect={onStationSelect}
              isLoading={isLoadingStations}
              placeholder="Choose a station to explore..."
            />
          </div>

          {isLoadingStations && (
            <div className="text-center text-sm text-gray-600">
              Loading available stations...
            </div>
          )}

          {!isLoadingStations && availableStations.length > 0 && (
            <div className="p-4 bg-blue-50 rounded-lg text-sm">
              <h4 className="font-semibold mb-2">Getting Started</h4>
              <p className="text-gray-700">
                Select a station from the dropdown above to view all direct
                train connections from that station. Data is pre-computed for
                instant loading.
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-gray-50 p-6 overflow-y-auto">
      <h2 className="text-2xl font-bold mb-2">Train Network Explorer</h2>
      <p className="text-sm text-gray-600 mb-4">
        From {selectedStation?.name || "Unknown Station"}
      </p>

      {/* Station Selector */}
      <div className="bg-white rounded-lg p-4 mb-6 shadow">
        <label className="block text-sm font-medium mb-2">Change Station</label>
        <StationSelector
          stations={availableStations}
          selectedStation={selectedStation}
          onSelect={onStationSelect}
          isLoading={isLoadingStations}
          placeholder="Select another station..."
        />
      </div>

      {/* Statistics */}
      <div className="bg-white rounded-lg p-4 mb-6 shadow">
        <h3 className="font-bold mb-3">Statistics</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Direct Connections:</span>
            <span className="font-semibold">{stats?.totalConnections || 0}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Filtered Connections:</span>
            <span className="font-semibold">
              {stats?.filteredConnections || 0}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Average Speed:</span>
            <span className="font-semibold">
              {formatSpeed(stats?.avgSpeed || 0)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Max Speed:</span>
            <span className="font-semibold">
              {formatSpeed(stats?.maxSpeed || 0)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Max Distance:</span>
            <span className="font-semibold">
              {formatDistance(stats?.maxDistance || 0)}
            </span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg p-4 mb-6 shadow">
        <h3 className="font-bold mb-3">Filters</h3>

        <div className="space-y-4">
          {/* Minimum speed slider */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Minimum Aerial Speed: {formatSpeed(minSpeed)}
            </label>
            <input
              type="range"
              min="0"
              max={Math.ceil(stats?.maxSpeed || 300)}
              step="10"
              value={minSpeed}
              onChange={(e) => onMinSpeedChange(Number(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0 km/h</span>
              <span>{Math.ceil(stats?.maxSpeed || 300)} km/h</span>
            </div>
          </div>
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

        <div className="p-4 bg-green-50 rounded-lg text-sm">
          <h4 className="font-semibold mb-2">Pre-computed Data</h4>
          <p className="text-gray-700">
            Connection data is pre-computed for fast loading. The displayed
            speeds represent the fastest connection available for each
            destination.
          </p>
        </div>
      </div>
    </div>
  );
}
