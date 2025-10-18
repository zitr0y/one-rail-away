"""
Service for fetching and processing train network data.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from geopy.distance import geodesic
import asyncio

from core.db_api_client import DBAPIClient
from core.models import Station, Connection, NetworkData


class NetworkService:
    """Service for building train network maps."""

    def __init__(self, api_client: Optional[DBAPIClient] = None):
        """
        Initialize the network service.

        Args:
            api_client: DB API client instance
        """
        self.api_client = api_client or DBAPIClient()

    async def get_station_info(self, station_name: str) -> Optional[Station]:
        """
        Get station information including coordinates.

        Args:
            station_name: Name of the station

        Returns:
            Station model or None if not found
        """
        station_data = await self.api_client.get_station_by_name(station_name)
        if not station_data:
            return None

        # New API client already returns lat/lon in the station data
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
        """
        Fetch complete network data for a station.

        Args:
            station_name: Name of the origin station
            max_connections: Maximum number of connections to fetch (None = all)

        Returns:
            NetworkData with all connections and statistics
        """
        # Get origin station info
        origin_station = await self.get_station_info(station_name)
        if not origin_station:
            raise ValueError(f"Station '{station_name}' not found")

        # Fetch departures for the day
        departures = await self.api_client.get_departures(origin_station.id)

        # Process departures to get unique connections
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
        """
        Process departure data into Connection objects.

        Args:
            origin_station: The origin station
            departures: List of departure dictionaries from API
            max_connections: Maximum connections to process

        Returns:
            List of Connection objects
        """
        connections = []
        seen_destinations: Set[str] = set()
        destination_cache: Dict[str, Station] = {}

        for departure in departures[:max_connections] if max_connections else departures:
            try:
                # Extract destination station name
                destination_name = self._extract_destination_name(departure)
                if not destination_name:
                    continue

                # Skip if we've already seen this destination
                # (we only want one connection per destination for now)
                if destination_name in seen_destinations:
                    continue

                # Get journey details to find final destination and arrival time
                journey_id = departure.get("JourneyDetailRef", {}).get("ref") or departure.get("detailsId")
                if not journey_id:
                    # If no journey details available, skip
                    continue

                journey_details = await self.api_client.get_journey_details(journey_id)
                if not journey_details:
                    continue

                # Find the final stop in journey
                final_stop = self._find_final_stop(journey_details, destination_name)
                if not final_stop:
                    continue

                # Get or fetch destination station info
                if destination_name not in destination_cache:
                    dest_station = await self.get_station_info(destination_name)
                    if not dest_station:
                        continue
                    destination_cache[destination_name] = dest_station
                else:
                    dest_station = destination_cache[destination_name]

                # Parse times
                dep_date = departure.get("date", "")
                dep_time = departure.get("time", "")
                arr_date = final_stop.get("date", dep_date)
                arr_time = final_stop.get("arrTime", final_stop.get("time", ""))

                if not dep_time or not arr_time:
                    continue

                departure_datetime = self.api_client.parse_datetime(dep_date, dep_time)
                arrival_datetime = self.api_client.parse_datetime(arr_date, arr_time)

                # Calculate travel time
                travel_time = arrival_datetime - departure_datetime
                travel_time_minutes = int(travel_time.total_seconds() / 60)

                if travel_time_minutes <= 0:
                    continue

                # Calculate distance and aerial speed
                distance_km = self._calculate_distance(
                    origin_station.lat, origin_station.lon,
                    dest_station.lat, dest_station.lon
                )

                if distance_km <= 0:
                    continue

                aerial_speed_kmh = (distance_km / travel_time_minutes) * 60

                # Extract train information
                train_type = self._extract_train_type(departure)
                train_number = departure.get("trainNumber") or departure.get("number")

                # Create connection
                connection = Connection(
                    origin_id=origin_station.id,
                    origin_name=origin_station.name,
                    destination_id=dest_station.id,
                    destination_name=dest_station.name,
                    train_type=train_type,
                    train_number=train_number,
                    departure_time=departure_datetime,
                    arrival_time=arrival_datetime,
                    travel_time_minutes=travel_time_minutes,
                    distance_km=round(distance_km, 2),
                    aerial_speed_kmh=round(aerial_speed_kmh, 2),
                    platform=departure.get("platform"),
                    delay=departure.get("delay")
                )

                connections.append(connection)
                seen_destinations.add(destination_name)

            except Exception as e:
                # Log error but continue processing other departures
                print(f"Error processing departure: {e}")
                continue

        return connections

    def _extract_destination_name(self, departure: Dict) -> Optional[str]:
        """Extract destination station name from departure data."""
        # Try different possible field names
        return (
            departure.get("direction") or
            departure.get("stop") or
            departure.get("station") or
            None
        )

    def _extract_train_type(self, departure: Dict) -> str:
        """Extract train type from departure data."""
        # Try different possible field names
        return (
            departure.get("type") or
            departure.get("category") or
            departure.get("trainCategory") or
            "UNKNOWN"
        )

    def _find_final_stop(self, journey_details: Dict, destination_name: str) -> Optional[Dict]:
        """
        Find the final stop in journey details that matches destination.

        Args:
            journey_details: Journey details from API
            destination_name: Expected destination name

        Returns:
            Stop dictionary or None
        """
        # Extract stops from journey details
        stops = []
        if isinstance(journey_details, dict):
            if "Stops" in journey_details:
                stops_data = journey_details["Stops"].get("Stop", [])
                stops = stops_data if isinstance(stops_data, list) else [stops_data]
            elif "stops" in journey_details:
                stops = journey_details["stops"]

        # Find matching destination stop
        for stop in reversed(stops):  # Check from end
            stop_name = stop.get("name", "")
            if destination_name.lower() in stop_name.lower():
                return stop

        # Return last stop if no match found
        return stops[-1] if stops else None

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate straight-line distance between two points.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in kilometers
        """
        if not all([lat1, lon1, lat2, lon2]):
            return 0.0

        try:
            return geodesic((lat1, lon1), (lat2, lon2)).kilometers
        except Exception:
            return 0.0
