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

import type { NetworkData, Connection, MultiHopRoute } from "@/types";
import {
  getSpeedColor,
  formatSpeed,
  formatDistance,
  formatDuration,
  getUniqueDestinations,
} from "@/lib/utils";

// Fix for default marker icons in Next.js
// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

// Custom icon for transfer/changeover stations
const transferIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

interface TrainNetworkMapProps {
  networkData: NetworkData;
  minSpeed: number;
  onStationClick?: (stationName: string) => void;
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
  onStationClick,
}: TrainNetworkMapProps) {
  const [filteredConnections, setFilteredConnections] = useState<Connection[]>([]);
  const [filteredMultiHopRoutes, setFilteredMultiHopRoutes] = useState<MultiHopRoute[]>([]);

  useEffect(() => {
    // Filter and get unique destinations for direct connections
    const uniqueConnections = getUniqueDestinations(networkData.connections);

    // Filter by min speed
    const filtered = uniqueConnections.filter(
      (c) => c.aerial_speed_kmh >= minSpeed
    );

    setFilteredConnections(filtered);

    // Filter multi-hop routes by min speed
    const filteredMultiHop = (networkData.multi_hop_routes || []).filter(
      (route) => route.average_aerial_speed_kmh >= minSpeed
    );

    setFilteredMultiHopRoutes(filteredMultiHop);
  }, [networkData, minSpeed]);

  const origin = networkData.origin_station;
  const center: [number, number] = [origin.lat, origin.lon];

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
              <h3 className="font-bold">{origin.name}</h3>
              <p>Origin Station</p>
              <p>Connections: {networkData.total_connections}</p>
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

          // Build route through waypoints
          const routePositions: [number, number][] = [center]; // Start at origin

          // Add all waypoints
          if (conn.route_waypoints && conn.route_waypoints.length > 0) {
            conn.route_waypoints.forEach((waypoint) => {
              routePositions.push([waypoint.lat, waypoint.lon]);
            });
          }

          // End at destination
          routePositions.push(destPos);

          return (
            <div key={`${conn.destination_id}-${idx}`}>
              {/* Connection line through waypoints */}
              <Polyline
                positions={routePositions}
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
                    {onStationClick && (
                      <button
                        onClick={() => onStationClick(conn.destination_name)}
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

        {/* Multi-hop routes with progressive dashing */}
        {filteredMultiHopRoutes.map((route, routeIdx) => {
          // Skip routes without valid coordinates
          if (!route.destination_lat || !route.destination_lon ||
              (route.destination_lat === 0 && route.destination_lon === 0)) {
            return null;
          }

          const destPos: [number, number] = [route.destination_lat, route.destination_lon];
          const color = getSpeedColor(
            route.average_aerial_speed_kmh,
            minSpeedValue,
            maxSpeedValue
          );

          // Progressive dashing: more changeovers = more dashed
          // dashArray format: [dash length, gap length]
          const dashArray = route.number_of_changeovers === 0
            ? undefined // Solid line for direct
            : route.number_of_changeovers === 1
            ? "10, 10" // Moderate dashing
            : route.number_of_changeovers === 2
            ? "8, 12" // More dashed
            : route.number_of_changeovers === 3
            ? "6, 14" // Very dashed
            : "4, 16"; // Extremely dashed (4+ changeovers)

          return (
            <div key={`multihop-${route.destination_id}-${routeIdx}`}>
              {/* Draw each leg of the route */}
              {route.legs.map((leg, legIdx) => {
                // For each leg, we need to find the coordinates
                // We'll use the origin station coordinates for the first leg
                // and the transfer station coordinates for subsequent legs
                const legOriginPos: [number, number] = legIdx === 0
                  ? center // First leg starts at origin
                  : route.transfers[legIdx - 1]
                  ? [route.transfers[legIdx - 1].station_lat, route.transfers[legIdx - 1].station_lon]
                  : center;

                const legDestPos: [number, number] = legIdx < route.transfers.length
                  ? [route.transfers[legIdx].station_lat, route.transfers[legIdx].station_lon]
                  : destPos; // Last leg ends at final destination

                return (
                  <Polyline
                    key={`leg-${legIdx}`}
                    positions={[legOriginPos, legDestPos]}
                    color={color}
                    weight={2}
                    opacity={0.5}
                    dashArray={dashArray}
                  />
                );
              })}

              {/* Transfer/changeover station markers */}
              {route.transfers.map((transfer, transferIdx) => (
                <Marker
                  key={`transfer-${transferIdx}`}
                  position={[transfer.station_lat, transfer.station_lon]}
                  icon={transferIcon}
                >
                  <Popup>
                    <div className="text-sm">
                      <h3 className="font-bold">{transfer.station_name}</h3>
                      <div className="text-xs text-orange-600 font-semibold mb-2">
                        Transfer Station
                      </div>
                      <div className="space-y-1 mt-2">
                        <p>
                          <span className="font-semibold">Arrival:</span>{" "}
                          {new Date(transfer.arrival_time).toLocaleTimeString()}
                        </p>
                        <p>
                          <span className="font-semibold">Departure:</span>{" "}
                          {new Date(transfer.departure_time).toLocaleTimeString()}
                        </p>
                        <p>
                          <span className="font-semibold">Transfer Time:</span>{" "}
                          {formatDuration(transfer.waiting_time_minutes)}
                        </p>
                        {transfer.arrival_platform && (
                          <p>
                            <span className="font-semibold">Platform:</span>{" "}
                            {transfer.arrival_platform} → {transfer.departure_platform}
                          </p>
                        )}
                      </div>
                      {onStationClick && (
                        <button
                          onClick={() => onStationClick(transfer.station_name)}
                          className="mt-3 w-full bg-orange-600 text-white px-3 py-1.5 rounded hover:bg-orange-700 transition-colors text-xs font-medium"
                        >
                          Set as Origin Station
                        </button>
                      )}
                    </div>
                  </Popup>
                </Marker>
              ))}

              {/* Destination marker for multi-hop route */}
              <Marker position={destPos}>
                <Popup>
                  <div className="text-sm">
                    <h3 className="font-bold">{route.destination_name}</h3>
                    <div className="text-xs text-gray-500 mb-2">
                      Multi-hop route ({route.number_of_changeovers} changeover{route.number_of_changeovers !== 1 ? 's' : ''})
                    </div>
                    <div className="space-y-1 mt-2">
                      <p>
                        <span className="font-semibold">Total Distance:</span>{" "}
                        {formatDistance(route.total_distance_km)}
                      </p>
                      <p>
                        <span className="font-semibold">Total Duration:</span>{" "}
                        {formatDuration(route.total_travel_time_minutes)}
                      </p>
                      <p>
                        <span className="font-semibold">Transfer Time:</span>{" "}
                        {formatDuration(route.total_waiting_time_minutes)}
                      </p>
                      <p>
                        <span className="font-semibold">Avg Speed:</span>{" "}
                        <span
                          style={{
                            color: color,
                            fontWeight: "bold",
                          }}
                        >
                          {formatSpeed(route.average_aerial_speed_kmh)}
                        </span>
                      </p>
                      <div className="mt-2 pt-2 border-t border-gray-200">
                        <p className="font-semibold mb-1">Route:</p>
                        <ol className="text-xs space-y-0.5">
                          {route.legs.map((leg, idx) => (
                            <li key={idx}>
                              {idx + 1}. {leg.train_type} {leg.train_number || ""} to {leg.destination_name}
                            </li>
                          ))}
                        </ol>
                      </div>
                    </div>
                    {onStationClick && (
                      <button
                        onClick={() => onStationClick(route.destination_name)}
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

        {/* Line styles */}
        <div className="mb-3">
          <p className="text-xs font-semibold mb-1">Connections:</p>
          <div className="space-y-1 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-8 h-0.5 bg-gray-400" />
              <span>Direct</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-0.5 bg-gray-400" style={{ backgroundImage: "repeating-linear-gradient(to right, #9ca3af 0, #9ca3af 5px, transparent 5px, transparent 10px)" }} />
              <span>1 transfer</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-0.5 bg-gray-400" style={{ backgroundImage: "repeating-linear-gradient(to right, #9ca3af 0, #9ca3af 4px, transparent 4px, transparent 10px)" }} />
              <span>2+ transfers</span>
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
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-orange-500 rounded-full" />
              <span>Transfer Point</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
