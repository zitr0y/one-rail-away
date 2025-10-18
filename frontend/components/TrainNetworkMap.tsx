"use client";

/**
 * Map component for visualizing train network connections
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

import type { NetworkData, Connection } from "@/types";
import {
  getSpeedColor,
  formatSpeed,
  formatDistance,
  formatDuration,
  getUniqueDestinations,
} from "@/lib/utils";

// Fix for default marker icons in Next.js
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

interface TrainNetworkMapProps {
  networkData: NetworkData;
  minSpeed: number;
}

interface DestinationWithCoords extends Connection {
  destination_lat: number;
  destination_lon: number;
}

function MapUpdater({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [map, center, zoom]);
  return null;
}

export default function TrainNetworkMap({
  networkData,
  minSpeed,
}: TrainNetworkMapProps) {
  const [destinationsWithCoords, setDestinationsWithCoords] = useState<
    DestinationWithCoords[]
  >([]);

  useEffect(() => {
    // Filter and get unique destinations
    const uniqueConnections = getUniqueDestinations(networkData.connections);

    // Filter by min speed
    const filtered = uniqueConnections.filter(
      (c) => c.aerial_speed_kmh >= minSpeed
    );

    // For now, we need to get destination coordinates
    // In a real implementation, we would fetch these from the backend
    // For now, we'll use a simple approach - we can enhance this later
    const withCoords = filtered.map((conn) => ({
      ...conn,
      destination_lat: 0, // Placeholder
      destination_lon: 0, // Placeholder
    }));

    setDestinationsWithCoords(withCoords);
  }, [networkData, minSpeed]);

  const origin = networkData.origin_station;
  const center: [number, number] = [origin.lat, origin.lon];

  // Calculate min/max speeds for color coding
  const speeds = destinationsWithCoords.map((c) => c.aerial_speed_kmh);
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
              <h3 className="font-bold">{origin.name}</h3>
              <p>Origin Station</p>
              <p>Connections: {networkData.total_connections}</p>
            </div>
          </Popup>
        </Marker>

        {/* Connection lines and destination markers */}
        {destinationsWithCoords.map((conn, idx) => {
          if (conn.destination_lat === 0 && conn.destination_lon === 0) {
            // Skip connections without valid coordinates
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
                        {conn.train_type} {conn.train_number || ""}
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
                    </div>
                  </div>
                </Popup>
              </Marker>
            </div>
          );
        })}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 bg-white p-4 rounded-lg shadow-lg z-[1000]">
        <h4 className="font-bold text-sm mb-2">Speed Legend</h4>
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-1">
            <div
              className="w-4 h-4 rounded"
              style={{ backgroundColor: "rgb(255, 0, 0)" }}
            />
            <span>Slow</span>
          </div>
          <div className="flex items-center gap-1">
            <div
              className="w-4 h-4 rounded"
              style={{ backgroundColor: "rgb(255, 255, 0)" }}
            />
            <span>Medium</span>
          </div>
          <div className="flex items-center gap-1">
            <div
              className="w-4 h-4 rounded"
              style={{ backgroundColor: "rgb(0, 255, 0)" }}
            />
            <span>Fast</span>
          </div>
        </div>
      </div>
    </div>
  );
}
