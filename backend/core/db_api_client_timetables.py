"""
Deutsche Bahn Timetables API client (IRIS format).
This API uses EVA numbers and plan/fchg endpoints.
"""
import httpx
import xmltodict
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from config import config


# Hardcoded EVA numbers for major German stations
STATION_EVA_NUMBERS = {
    "Essen Hbf": "8000098",
    "Berlin Hbf": "8011160",
    "München Hbf": "8000261",
    "Hamburg Hbf": "8002549",
    "Frankfurt(Main)Hbf": "8000105",
    "Köln Hbf": "8000207",
    "Düsseldorf Hbf": "8000085",
    "Stuttgart Hbf": "8000096",
    "Hannover Hbf": "8000152",
    "Nürnberg Hbf": "8000284",
}


class DBAPIClient:
    """Client for interacting with the Deutsche Bahn Timetables API (IRIS format)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the DB API client.

        Args:
            api_key: DB API key (defaults to config.DB_API_KEY)
            base_url: API base URL (defaults to config.DB_API_BASE_URL)
        """
        self.api_key = api_key or config.DB_API_KEY
        self.base_url = base_url or config.DB_API_BASE_URL
        # Try standard Authorization Bearer token
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

    def get_station_eva(self, station_name: str) -> Optional[str]:
        """
        Get EVA number for a station from our hardcoded list.

        Args:
            station_name: Station name

        Returns:
            EVA number or None if not found
        """
        # Try exact match first
        if station_name in STATION_EVA_NUMBERS:
            return STATION_EVA_NUMBERS[station_name]

        # Try case-insensitive match
        for name, eva in STATION_EVA_NUMBERS.items():
            if name.lower() == station_name.lower():
                return eva

        # Try partial match
        for name, eva in STATION_EVA_NUMBERS.items():
            if station_name.lower() in name.lower() or name.lower() in station_name.lower():
                return eva

        return None

    async def get_station_info(self, station_name: str) -> Optional[Dict[str, Any]]:
        """
        Get station information.

        Args:
            station_name: Station name

        Returns:
            Station dict with id, name, lat, lon
        """
        eva = self.get_station_eva(station_name)
        if not eva:
            return None

        # Hardcoded coordinates for major stations
        coords = {
            "8000098": (51.4508, 7.0131),  # Essen Hbf
            "8011160": (52.5250, 13.3694),  # Berlin Hbf
            "8000261": (48.1402, 11.5582),  # München Hbf
            "8002549": (53.5528, 10.0067),  # Hamburg Hbf
            "8000105": (50.1070, 8.6632),   # Frankfurt Hbf
            "8000207": (50.9432, 6.9589),   # Köln Hbf
            "8000085": (51.2199, 6.7942),   # Düsseldorf Hbf
            "8000096": (48.7840, 9.1816),   # Stuttgart Hbf
            "8000152": (52.3765, 9.7410),   # Hannover Hbf
            "8000284": (49.4458, 11.0831),  # Nürnberg Hbf
        }

        lat, lon = coords.get(eva, (0.0, 0.0))

        return {
            "id": eva,
            "name": station_name,
            "lat": lat,
            "lon": lon,
        }

    async def get_plan_data(
        self,
        eva_number: str,
        date_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get planned timetable data for a station.

        Args:
            eva_number: Station EVA number
            date_time: DateTime to fetch (defaults to now)

        Returns:
            List of train stop dictionaries
        """
        if date_time is None:
            date_time = datetime.now()

        # Format: YYMMDD/HH
        date_str = date_time.strftime("%y%m%d")
        hour_str = date_time.strftime("%H")

        url = f"{self.base_url}/plan/{eva_number}/{date_str}/{hour_str}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()

            # Parse XML response
            data = xmltodict.parse(response.text)

            # Extract train stops
            stops = []
            if "timetable" in data and "s" in data["timetable"]:
                s_data = data["timetable"]["s"]
                if isinstance(s_data, list):
                    stops = s_data
                else:
                    stops = [s_data]

            return stops

    async def get_departures(
        self,
        station_id: str,
        date: Optional[str] = None,
        time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get departures for a station (wraps get_plan_data).

        Args:
            station_id: EVA number
            date: Date (ignored, uses current)
            time: Time (ignored, uses current)

        Returns:
            List of departure dictionaries
        """
        # Get data for current hour and next hour
        now = datetime.now()
        current_hour_data = await self.get_plan_data(station_id, now)
        next_hour_data = await self.get_plan_data(station_id, now + timedelta(hours=1))

        all_stops = current_hour_data + next_hour_data

        # Filter for departures only and convert format
        departures = []
        for stop in all_stops:
            # Check if train departs from this station
            if "dp" not in stop:
                continue

            dp = stop["dp"]

            # Extract train information
            train_info = stop.get("tl", {})

            departure = {
                "id": stop.get("id", ""),
                "type": train_info.get("@c", ""),  # Train category (ICE, IC, etc.)
                "number": train_info.get("@n", ""),  # Train number
                "direction": dp.get("@ppth", "").split("|")[-1] if dp.get("@ppth") else "",  # Last station in path
                "platform": dp.get("@pp", ""),  # Planned platform
                "time": dp.get("@pt", ""),  # Planned time (YYMMDDhhmm format)
                "path": dp.get("@ppth", ""),  # Full path
            }

            departures.append(departure)

        return departures

    def parse_iris_time(self, time_str: str) -> datetime:
        """
        Parse IRIS time format (YYMMDDhhmm) to datetime.

        Args:
            time_str: Time string in YYMMDDhhmm format

        Returns:
            datetime object
        """
        try:
            return datetime.strptime(time_str, "%y%m%d%H%M")
        except:
            return datetime.now()

    async def search_station(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for stations (returns from hardcoded list).

        Args:
            query: Station name to search

        Returns:
            List of matching stations
        """
        results = []
        query_lower = query.lower()

        for name, eva in STATION_EVA_NUMBERS.items():
            if query_lower in name.lower():
                station_info = await self.get_station_info(name)
                if station_info:
                    results.append(station_info)

        return results

    async def get_station_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get station by name.

        Args:
            name: Station name

        Returns:
            Station dictionary
        """
        return await self.get_station_info(name)
