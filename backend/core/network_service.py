"""
Simplified service for fetching and processing train network data.
Works with the DB Timetables API /plan endpoint.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from geopy.distance import geodesic

from core.db_api_client import DBAPIClient
from core.models import Station, Connection, NetworkData


class NetworkService:
    """Service for building train network maps."""

    def __init__(self, api_client: Optional[DBAPIClient] = None):
        """Initialize the network service."""
        self.api_client = api_client or DBAPIClient()

    async def get_station_info(self, station_name: str) -> Optional[Station]:
        """Get station information including coordinates."""
        station_data = await self.api_client.get_station_by_name(station_name)
        if not station_data:
            return None

        return Station(
            id=station_data.get("id", ""),
            name=station_data.get("name", station_name),
            lat=station_data.get("lat", 0.0),
            lon=station_data.get("lon", 0.0)
        )

    async def fetch_network_data(
        self,
        station_name: str = "Essen Hbf",
        max_connections: Optional[int] = None
    ) -> NetworkData:
        """Fetch complete network data for a station."""
        # Get origin station info
        origin_station = await self.get_station_info(station_name)
        if not origin_station:
            raise ValueError(f"Station '{station_name}' not found")

        # Fetch departures
        departures = await self.api_client.get_departures(origin_station.id)

        # Process departures to get connections
        connections = await self._process_departures(
            origin_station,
            departures,
            max_connections
        )

        # Create network data object
        network_data = NetworkData(
            origin_station=origin_station,
            connections=connections
        )

        # Calculate statistics
        network_data.calculate_statistics()

        return network_data

    async def _process_departures(
        self,
        origin_station: Station,
        departures: List[Dict],
        max_connections: Optional[int] = None
    ) -> List[Connection]:
        """Process departure data into Connection objects."""
        connections = []
        seen_pairs: Set[tuple] = set()  # Track (train_number, destination) pairs

        for departure in departures[:max_connections] if max_connections else departures:
            try:
                # Get all stations in the path for this train
                path_stations = departure.get("path_stations", [])
                if not path_stations:
                    # Fallback to just destination
                    path_stations = [departure.get("destination", "")]

                train_number = departure.get("number", "")
                train_type = departure.get("type", "")

                # Parse departure time from format: YYMMDDhhmm
                time_str = departure.get("time", "")
                if len(time_str) != 10:
                    continue

                try:
                    departure_datetime = datetime.strptime(time_str, "%y%m%d%H%M")
                except ValueError:
                    continue

                # Check each station in the path
                for dest_name in path_stations:
                    # Create unique key
                    pair_key = (train_number, dest_name)
                    if pair_key in seen_pairs:
                        continue

                    # Get destination station info
                    dest_station = await self.get_station_info(dest_name)
                    if not dest_station or (dest_station.lat == 0.0 and dest_station.lon == 0.0):
                        # Skip if we don't have coordinates
                        continue

                    # Calculate distance
                    distance_km = self._calculate_distance(
                        origin_station.lat, origin_station.lon,
                        dest_station.lat, dest_station.lon
                    )

                    if distance_km <= 0:
                        continue

                    # Estimate travel time based on train type
                    avg_speed = self._estimate_speed(train_type)
                    travel_time_minutes = int((distance_km / avg_speed) * 60)

                    if travel_time_minutes <= 0:
                        continue

                    arrival_datetime = departure_datetime + timedelta(minutes=travel_time_minutes)
                    aerial_speed_kmh = (distance_km / travel_time_minutes) * 60

                    # Create connection
                    connection = Connection(
                        origin_id=origin_station.id,
                        origin_name=origin_station.name,
                        destination_id=dest_station.id,
                        destination_name=dest_station.name,
                        destination_lat=dest_station.lat,
                        destination_lon=dest_station.lon,
                        train_type=train_type,
                        train_number=train_number,
                        departure_time=departure_datetime,
                        arrival_time=arrival_datetime,
                        travel_time_minutes=travel_time_minutes,
                        distance_km=round(distance_km, 2),
                        aerial_speed_kmh=round(aerial_speed_kmh, 2),
                        platform=departure.get("platform"),
                        delay=None,
                    )

                    connections.append(connection)
                    seen_pairs.add(pair_key)

            except Exception as e:
                print(f"Error processing departure: {e}")
                continue

        return connections

    def _estimate_speed(self, train_type: str) -> float:
        """Estimate average speed based on train type."""
        speeds = {
            "ICE": 200.0,  # High-speed trains
            "IC": 150.0,   # Intercity
            "EC": 150.0,   # EuroCity
            "RE": 100.0,   # Regional Express
            "RB": 80.0,    # Regional train
            "S": 60.0,     # S-Bahn
        }
        print("the speeds are a lie!")
        return speeds.get(train_type, 100.0)

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate straight-line distance between two points."""
        if not all([lat1, lon1, lat2, lon2]):
            return 0.0

        try:
            return geodesic((lat1, lon1), (lat2, lon2)).kilometers
        except Exception:
            return 0.0
