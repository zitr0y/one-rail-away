"""
Deutsche Bahn API client using bahnhof.de API.
This API is simpler, doesn't require authentication, and returns JSON.
Based on: https://www.reddit.com/r/bahn/comments/1at4lxs/timetables_api_doku/
"""
import httpx
from typing import Optional, List, Dict, Any
from datetime import datetime
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

# Hardcoded coordinates for major stations
STATION_COORDS = {
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


class DBAPIClient:
    """Client for Deutsche Bahn data using bahnhof.de API (no auth required!)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the API client.
        Note: api_key and base_url are kept for compatibility but not used.
        The bahnhof.de API doesn't require authentication.
        """
        self.base_url = "https://www.bahnhof.de/api/boards"

    def get_station_eva(self, station_name: str) -> Optional[str]:
        """Get EVA number for a station from our hardcoded list."""
        # Try exact match
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
        """Get station information including coordinates."""
        eva = self.get_station_eva(station_name)
        if not eva:
            return None

        lat, lon = STATION_COORDS.get(eva, (0.0, 0.0))

        return {
            "id": eva,
            "name": station_name,
            "lat": lat,
            "lon": lon,
        }

    async def get_departures(
        self,
        station_id: str,
        date: Optional[str] = None,
        time: Optional[str] = None,
        duration: int = 120
    ) -> List[Dict[str, Any]]:
        """
        Get departures for a station.

        Args:
            station_id: EVA number
            date: Date (ignored, uses current time)
            time: Time (ignored, uses current time)
            duration: How many minutes of departures to fetch (default 120 = 2 hours)

        Returns:
            List of departure dictionaries
        """
        # Build params - filterTransports needs to be repeated, not as array
        params = [
            ("evaNumbers", station_id),
            ("filterTransports", "HIGH_SPEED_TRAIN"),
            ("filterTransports", "INTERCITY_TRAIN"),
            ("filterTransports", "INTER_REGIONAL_TRAIN"),
            ("filterTransports", "REGIONAL_TRAIN"),
            ("filterTransports", "CITY_TRAIN"),
            ("duration", str(duration)),
            ("stationCategory", "1"),  # Category 1 = major stations
            ("locale", "de"),
            ("sortBy", "TIME_SCHEDULE"),
        ]

        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/departures"
            print(f"DEBUG: Requesting {url}")
            print(f"DEBUG: Params: {params}")

            response = await client.get(
                url,
                params=params,
                timeout=30.0
            )

            print(f"DEBUG: Status Code: {response.status_code}")
            print(f"DEBUG: Response URL: {response.url}")
            print(f"DEBUG: Response Headers: {dict(response.headers)}")
            print(f"DEBUG: Response Text (first 500 chars): {response.text[:500]}")

            response.raise_for_status()
            data = response.json()

            # Extract departures from response
            departures = []
            if isinstance(data, dict) and "departures" in data:
                raw_departures = data["departures"]
            elif isinstance(data, list):
                raw_departures = data
            else:
                raw_departures = []

            # Convert to our format
            for dep in raw_departures:
                departure = {
                    "id": dep.get("id", ""),
                    "type": dep.get("transport", {}).get("category", ""),
                    "number": dep.get("transport", {}).get("number", ""),
                    "direction": dep.get("direction", ""),
                    "platform": dep.get("platform", {}).get("name", ""),
                    "time": dep.get("departureTime", {}).get("scheduledTime", ""),
                    "delay": dep.get("departureTime", {}).get("delay"),
                    "destination": dep.get("destination", {}).get("name", dep.get("direction", "")),
                }
                departures.append(departure)

            return departures

    async def search_station(self, query: str) -> List[Dict[str, Any]]:
        """Search for stations (returns from hardcoded list)."""
        results = []
        query_lower = query.lower()

        for name, eva in STATION_EVA_NUMBERS.items():
            if query_lower in name.lower():
                station_info = await self.get_station_info(name)
                if station_info:
                    results.append(station_info)

        return results

    async def get_station_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get station by name."""
        return await self.get_station_info(name)
