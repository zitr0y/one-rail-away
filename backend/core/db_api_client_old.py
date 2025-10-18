"""
Deutsche Bahn API client for fetching timetable data.
"""
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime
from config import config


class DBAPIClient:
    """Client for interacting with the Deutsche Bahn Timetables API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the DB API client.

        Args:
            api_key: DB API key (defaults to config.DB_API_KEY)
            base_url: API base URL (defaults to config.DB_API_BASE_URL)
        """
        self.api_key = api_key or config.DB_API_KEY
        self.base_url = base_url or config.DB_API_BASE_URL
        # DB API Marketplace uses DB-Client-Id and DB-Api-Key headers
        # Some endpoints might also work with just DB-Api-Key
        self.headers = {
            "DB-Client-Id": self.api_key,
            "DB-Api-Key": self.api_key,
            "Accept": "application/json"
        }

    async def search_station(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for a station by name.

        Args:
            query: Station name to search for

        Returns:
            List of station dictionaries with id, name, and location data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/location.name",
                headers=self.headers,
                params={"input": query},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            # The API returns a list of locations
            # Filter for stations (type == "ST")
            stations = []
            if isinstance(data, list):
                stations = [loc for loc in data if loc.get("type") == "ST"]
            elif isinstance(data, dict) and "LocationList" in data:
                # Alternative response format
                location_list = data["LocationList"].get("StopLocation", [])
                stations = location_list if isinstance(location_list, list) else [location_list]

            return stations

    async def get_station_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific station by exact or close name match.

        Args:
            name: Station name

        Returns:
            Station dictionary or None if not found
        """
        stations = await self.search_station(name)
        if not stations:
            return None

        # Try to find exact match first
        for station in stations:
            station_name = station.get("name", "")
            if station_name.lower() == name.lower():
                return station

        # Return first result if no exact match
        return stations[0] if stations else None

    async def get_departures(
        self,
        station_id: str,
        date: Optional[str] = None,
        time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get departure board for a station.

        Args:
            station_id: Station ID
            date: Date in YYYY-MM-DD format (defaults to today)
            time: Time in HH:MM format (defaults to now)

        Returns:
            List of departure dictionaries
        """
        params = {"id": station_id}

        if date:
            params["date"] = date
        if time:
            params["time"] = time

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/departureBoard",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            # Extract departures from response
            departures = []
            if isinstance(data, list):
                departures = data
            elif isinstance(data, dict):
                # Handle different response formats
                if "Departure" in data:
                    dep_data = data["Departure"]
                    departures = dep_data if isinstance(dep_data, list) else [dep_data]
                elif "DepartureBoard" in data:
                    dep_board = data["DepartureBoard"]
                    if "Departure" in dep_board:
                        dep_data = dep_board["Departure"]
                        departures = dep_data if isinstance(dep_data, list) else [dep_data]

            return departures

    async def get_journey_details(self, journey_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed journey information including all stops.

        Args:
            journey_id: Journey/trip ID from departure/arrival data

        Returns:
            Journey details dictionary
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/journeyDetail",
                headers=self.headers,
                params={"id": journey_id},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    def parse_station_location(self, station_data: Dict[str, Any]) -> tuple[float, float]:
        """
        Extract latitude and longitude from station data.

        Args:
            station_data: Station dictionary from API

        Returns:
            Tuple of (latitude, longitude)
        """
        # Try different possible location field names
        lat, lon = 0.0, 0.0

        if "lat" in station_data and "lon" in station_data:
            lat = float(station_data["lat"])
            lon = float(station_data["lon"])
        elif "Latitude" in station_data and "Longitude" in station_data:
            lat = float(station_data["Latitude"])
            lon = float(station_data["Longitude"])
        elif "location" in station_data:
            loc = station_data["location"]
            lat = float(loc.get("latitude", loc.get("lat", 0.0)))
            lon = float(loc.get("longitude", loc.get("lon", 0.0)))

        return lat, lon

    def parse_datetime(self, date_str: str, time_str: str) -> datetime:
        """
        Parse date and time strings to datetime object.

        Args:
            date_str: Date string (YYYY-MM-DD or DD.MM.YY)
            time_str: Time string (HH:MM)

        Returns:
            datetime object
        """
        # Handle different date formats
        try:
            # Try YYYY-MM-DD format
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                # Try DD.MM.YY format
                dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%y %H:%M")
            except ValueError:
                # Fallback to current time
                dt = datetime.now()

        return dt
