"""
Deutsche Bahn Timetables API client with proper authentication.
Uses the official DB API Marketplace Timetables API.
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
    """Client for Deutsche Bahn Timetables API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize the API client."""
        self.api_key = api_key or config.DB_API_KEY
        self.client_id = config.DB_CLIENT_ID
        self.base_url = base_url or config.DB_API_BASE_URL

        # DB API Marketplace authentication requires both Client ID and API Key
        self.headers = {
            "DB-Client-Id": self.client_id,
            "DB-Api-Key": self.api_key,
        }

    def get_station_eva(self, station_name: str) -> Optional[str]:
        """Get EVA number for a station from our hardcoded list."""
        if station_name in STATION_EVA_NUMBERS:
            return STATION_EVA_NUMBERS[station_name]

        for name, eva in STATION_EVA_NUMBERS.items():
            if name.lower() == station_name.lower():
                return eva

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
        Get departures for a station using the /plan endpoint.

        Args:
            station_id: EVA number
            date: Date (ignored, uses current time)
            time: Time (ignored, uses current time)
            duration: Minutes of departures (ignored, fetches current hour)

        Returns:
            List of departure dictionaries
        """
        now = datetime.now()

        # Format: YYMMDD/HH
        date_str = now.strftime("%y%m%d")
        hour_str = now.strftime("%H")

        url = f"{self.base_url}/plan/{station_id}/{date_str}/{hour_str}"

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
            departures = []
            if "timetable" in data and "s" in data["timetable"]:
                stops_data = data["timetable"]["s"]
                stops = stops_data if isinstance(stops_data, list) else [stops_data]

                for stop in stops:
                    # Only process departures (has 'dp' element)
                    if "dp" not in stop:
                        continue

                    dp = stop["dp"]
                    tl = stop.get("tl", {})

                    # Parse path to get destination
                    path = dp.get("@ppth", "")
                    destination = path.split("|")[-1] if path else ""

                    departure = {
                        "id": stop.get("@id", ""),
                        "type": tl.get("@c", ""),
                        "number": tl.get("@n", ""),
                        "direction": destination,
                        "platform": dp.get("@pp", ""),
                        "time": dp.get("@pt", ""),
                        "destination": destination,
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
