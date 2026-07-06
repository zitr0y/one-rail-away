"use client";

/**
 * Map component for visualizing train network connections (simplified - direct only)
 */

import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import type { StationSummary, PrecomputedConnection } from "@/types";
import {
  getSpeedColor,
  formatSpeed,
  formatDistance,
  formatDuration,
} from "@/lib/utils";

// Fix for default marker icons in Next.js
// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

interface TrainNetworkMapProps {
  originStation: StationSummary;
  connections: PrecomputedConnection[];
  minSpeed: number;
  onStationClick?: (stationId: string) => void;
}

function MapUpdater({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [map, center, zoom]);
  return null;
}

export default function TrainNetworkMap({
  originStation,
  connections,
  minSpeed,
  onStationClick,
}: TrainNetworkMapProps) {
  const [filteredConnections, setFilteredConnections] = useState<PrecomputedConnection[]>([]);

  useEffect(() => {
    // Filter by min speed
    const filtered = connections.filter(
      (c) => c.aerial_speed_kmh >= minSpeed
    );
    setFilteredConnections(filtered);
  }, [connections, minSpeed]);

  const center: [number, number] = [originStation.lat, originStation.lon];

  // Calculate min/max speeds for color coding
  const speeds = filteredConnections.map((c) => c.aerial_speed_kmh);
  const minSpeedValue = speeds.length > 0 ? Math.min(...speeds) : 0;
  const maxSpeedValue = speeds.length > 0 ? Math.max(...speeds) : 300;

  return (
    <div className="h-full w-full relative">
      <MapContainer
        center={center}
        zoom={7}
        className="h-full w-full"
        scrollWheelZoom={true}
      >
        <MapUpdater center={center} zoom={7} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Origin marker */}
        <Marker position={center}>
          <Popup>
            <div className="text-sm">
              <h3 className="font-bold">{originStation.name}</h3>
              <p>Origin Station</p>
              <p>Connections: {connections.length}</p>
            </div>
          </Popup>
        </Marker>

        {/* Connection lines and destination markers */}
        {filteredConnections.map((conn, idx) => {
          // Skip connections without valid coordinates
          if (!conn.destination_lat || !conn.destination_lon ||
              (conn.destination_lat === 0 && conn.destination_lon === 0)) {
            return null;
          }

          const destPos: [number, number] = [
            conn.destination_lat,
            conn.destination_lon,
          ];
          const color = getSpeedColor(
            conn.aerial_speed_kmh,
            minSpeedValue,
            maxSpeedValue
          );

          return (
            <div key={`${conn.destination_id}-${idx}`}>
              {/* Connection line */}
              <Polyline
                positions={[center, destPos]}
                color={color}
                weight={3}
                opacity={0.6}
              />

              {/* Destination marker */}
              <Marker position={destPos}>
                <Popup>
                  <div className="text-sm">
                    <h3 className="font-bold">{conn.destination_name}</h3>
                    <div className="space-y-1 mt-2">
                      <p>
                        <span className="font-semibold">Train:</span>{" "}
                        {conn.train_type} {conn.train_number}
                      </p>
                      <p>
                        <span className="font-semibold">Departure:</span>{" "}
                        {conn.departure_time} → {conn.arrival_time}
                      </p>
                      <p>
                        <span className="font-semibold">Distance:</span>{" "}
                        {formatDistance(conn.distance_km)}
                      </p>
                      <p>
                        <span className="font-semibold">Duration:</span>{" "}
                        {formatDuration(conn.travel_time_minutes)}
                      </p>
                      <p>
                        <span className="font-semibold">Aerial Speed:</span>{" "}
                        <span
                          style={{
                            color: color,
                            fontWeight: "bold",
                          }}
                        >
                          {formatSpeed(conn.aerial_speed_kmh)}
                        </span>
                      </p>
                      <p>
                        <span className="font-semibold">Daily Frequency:</span>{" "}
                        {conn.daily_frequency}
                      </p>
                    </div>
                    {onStationClick && (
                      <button
                        onClick={() => onStationClick(conn.destination_id)}
                        className="mt-3 w-full bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 transition-colors text-xs font-medium"
                      >
                        Set as Origin Station
                      </button>
                    )}
                  </div>
                </Popup>
              </Marker>
            </div>
          );
        })}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 bg-white p-4 rounded-lg shadow-lg z-[1000] max-w-xs">
        <h4 className="font-bold text-sm mb-2">Legend</h4>

        {/* Speed colors */}
        <div className="mb-3">
          <p className="text-xs font-semibold mb-1">Speed:</p>
          <div className="flex items-center gap-2 text-xs">
            <div className="flex items-center gap-1">
              <div
                className="w-3 h-3 rounded"
                style={{ backgroundColor: "rgb(255, 0, 0)" }}
              />
              <span>Slow</span>
            </div>
            <div className="flex items-center gap-1">
              <div
                className="w-3 h-3 rounded"
                style={{ backgroundColor: "rgb(255, 255, 0)" }}
              />
              <span>Medium</span>
            </div>
            <div className="flex items-center gap-1">
              <div
                className="w-3 h-3 rounded"
                style={{ backgroundColor: "rgb(0, 255, 0)" }}
              />
              <span>Fast</span>
            </div>
          </div>
        </div>

        {/* Marker types */}
        <div>
          <p className="text-xs font-semibold mb-1">Stations:</p>
          <div className="space-y-1 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-blue-500 rounded-full" />
              <span>Origin/Destination</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
