"""
Deutsche Bahn Timetables API client with proper authentication.
Uses the official DB API Marketplace Timetables API.
"""
import httpx
import xmltodict
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from config import config


def load_stations_database() -> tuple[Dict[str, Dict], Dict[str, Dict]]:
    """
    Load stations from stations.json file.
    Returns two dictionaries: one indexed by EVA number, one indexed by name.
    """
    stations_file = Path(__file__).parent.parent / "data" / "stations.json"

    eva_lookup = {}
    name_lookup = {}

    try:
        with open(stations_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            stations = data.get("stations", [])

            for station in stations:
                eva = str(station.get("eva", ""))
                name = station.get("name", "")
                lat = station.get("lat", 0.0)
                lon = station.get("lon", 0.0)
                meta_evas = station.get("meta_evas", [])

                if eva and name and lat and lon:
                    station_data = {
                        "eva": eva,
                        "name": name,
                        "lat": lat,
                        "lon": lon,
                        "meta_evas": [str(e) for e in meta_evas]  # Store related EVA numbers
                    }
                    eva_lookup[eva] = station_data
                    # Index by lowercase name for easier lookup
                    name_lookup[name.lower()] = station_data

            print(f"Loaded {len(eva_lookup)} stations from database")

    except Exception as e:
        print(f"Error loading stations database: {e}")
        # Return at least Essen Hbf as fallback
        fallback = {
            "8000098": {
                "eva": "8000098",
                "name": "Essen Hbf",
                "lat": 51.4508,
                "lon": 7.0131
            }
        }
        return fallback, {"essen hbf": fallback["8000098"]}

    return eva_lookup, name_lookup


# Load stations database once at module load
STATIONS_BY_EVA, STATIONS_BY_NAME = load_stations_database()


def get_all_related_evas(eva: str) -> List[str]:
    """
    Get all related EVA numbers for a station (including the station itself and its meta_evas).

    This handles station fragmentation where one logical station has multiple EVA numbers
    for different platforms/sections (e.g., Berlin Hbf, Berlin Hbf (S-Bahn), Berlin Hbf (tief)).

    Args:
        eva: The EVA number to lookup

    Returns:
        List of all related EVA numbers (including the input EVA)
    """
    related_evas = {eva}  # Start with the given EVA

    station_data = STATIONS_BY_EVA.get(eva)
    if station_data:
        # Add all meta_evas from this station
        meta_evas = station_data.get("meta_evas", [])
        related_evas.update(meta_evas)

    return list(related_evas)


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
        """Get EVA number for a station from our database."""
        # Try exact match first (case-insensitive)
        station_lower = station_name.lower()
        if station_lower in STATIONS_BY_NAME:
            return STATIONS_BY_NAME[station_lower]["eva"]

        # Try partial match
        for name, data in STATIONS_BY_NAME.items():
            if station_lower in name or name in station_lower:
                return data["eva"]

        return None

    async def get_station_info(self, station_name: str) -> Optional[Dict[str, Any]]:
        """Get station information including coordinates."""
        # Try to find station by name
        station_lower = station_name.lower()
        if station_lower in STATIONS_BY_NAME:
            station_data = STATIONS_BY_NAME[station_lower]
            return {
                "id": station_data["eva"],
                "name": station_data["name"],
                "lat": station_data["lat"],
                "lon": station_data["lon"],
            }

        # Try partial match
        for name, data in STATIONS_BY_NAME.items():
            if station_lower in name or name in station_lower:
                return {
                    "id": data["eva"],
                    "name": data["name"],
                    "lat": data["lat"],
                    "lon": data["lon"],
                }

        # Try by EVA number if provided
        eva = self.get_station_eva(station_name)
        if eva and eva in STATIONS_BY_EVA:
            station_data = STATIONS_BY_EVA[eva]
            return {
                "id": station_data["eva"],
                "name": station_data["name"],
                "lat": station_data["lat"],
                "lon": station_data["lon"],
            }

        return None

    async def get_departures(
        self,
        station_id: str,
        duration: int = 720  # 12 hours by default
    ) -> List[Dict[str, Any]]:
        """
        Get departures for a station using the /plan endpoint.
        Fetches multiple hours to get more comprehensive data.

        Args:
            station_id: EVA number
            date: Date (ignored, uses current time)
            time: Time (ignored, uses current time)
            duration: Minutes of departures (will fetch enough hours)

        Returns:
            List of departure dictionaries
        """
        now = datetime.now()
        hours_to_fetch = max(4, duration // 60)  # At least 4 hours

        all_departures = []

        # Fetch data for multiple hours
        for hour_offset in range(hours_to_fetch):
            try:
                fetch_time = now + timedelta(hours=hour_offset)
                date_str = fetch_time.strftime("%y%m%d")
                hour_str = fetch_time.strftime("%H")

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
                    timetable = data.get("timetable")
                    if timetable and isinstance(timetable, dict) and "s" in timetable:
                        stops_data = timetable["s"]
                        stops = stops_data if isinstance(stops_data, list) else [stops_data]

                        for stop in stops:
                            if not stop or not isinstance(stop, dict):
                                continue

                            # Only process departures (has 'dp' element)
                            if "dp" not in stop:
                                continue

                            dp = stop["dp"]
                            tl = stop.get("tl", {})

                            # Parse path to get all stations on route and destination
                            path = dp.get("@ppth", "")
                            path_stations = path.split("|") if path else []
                            destination = path_stations[-1] if path_stations else ""

                            departure = {
                                "id": stop.get("@id", ""),
                                "type": tl.get("@c", ""),
                                "number": tl.get("@n", ""),
                                "direction": destination,
                                "platform": dp.get("@pp", ""),
                                "time": dp.get("@pt", ""),
                                "destination": destination,
                                "path_stations": path_stations,  # Include full path!
                            }
                            all_departures.append(departure)

            except Exception as e:
                print(f"Error fetching hour {hour_offset}: {e}")
                continue

        return all_departures

    async def get_full_plan(
        self,
        station_id: str,
        date_str: str,
        hours: List[int] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get FULL plan data (both arrivals and departures) for a station.
        Used for matching arrival times at destination stations.

        Args:
            station_id: EVA number
            date_str: Date in YYMMDD format for the starting day
            hours: List of hours to fetch (0-23). If None, fetches all 24 hours.
                   Hours that wrap past midnight will automatically use the next day's date.

        Returns:
            Dict with 'arrivals' and 'departures' lists
        """
        if hours is None:
            hours = list(range(24))

        all_arrivals = []
        all_departures = []

        # Parse the base date
        base_date = datetime.strptime(date_str, "%y%m%d")
        current_hour = datetime.now().hour

        for hour in hours:
            try:
                # If this hour is less than the current hour and we're iterating forward,
                # it means we've wrapped to the next day
                if hour < current_hour and hours[0] >= current_hour:
                    # This hour is on the next day
                    fetch_date = base_date + timedelta(days=1)
                    fetch_date_str = fetch_date.strftime("%y%m%d")
                else:
                    fetch_date_str = date_str

                hour_str = f"{hour:02d}"
                url = f"{self.base_url}/plan/{station_id}/{fetch_date_str}/{hour_str}"

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
                    timetable = data.get("timetable")
                    if timetable and isinstance(timetable, dict) and "s" in timetable:
                        stops_data = timetable["s"]
                        stops = stops_data if isinstance(stops_data, list) else [stops_data]

                        for stop in stops:
                            if not stop or not isinstance(stop, dict):
                                continue

                            tl = stop.get("tl", {})
                            train_type = tl.get("@c", "")
                            train_number = tl.get("@n", "")

                            # Process arrivals
                            if "ar" in stop:
                                ar = stop["ar"]
                                path = ar.get("@ppth", "")
                                path_stations = path.split("|") if path else []

                                arrival = {
                                    "id": stop.get("@id", ""),
                                    "type": train_type,
                                    "number": train_number,
                                    "time": ar.get("@pt", ""),
                                    "platform": ar.get("@pp", ""),
                                    "path_stations": path_stations,
                                    "line": ar.get("@l", ""),
                                }
                                all_arrivals.append(arrival)

                            # Process departures
                            if "dp" in stop:
                                dp = stop["dp"]
                                path = dp.get("@ppth", "")
                                path_stations = path.split("|") if path else []
                                destination = path_stations[-1] if path_stations else ""

                                departure = {
                                    "id": stop.get("@id", ""),
                                    "type": train_type,
                                    "number": train_number,
                                    "direction": destination,
                                    "platform": dp.get("@pp", ""),
                                    "time": dp.get("@pt", ""),
                                    "destination": destination,
                                    "path_stations": path_stations,
                                }
                                all_departures.append(departure)

            except Exception as e:
                print(f"Error fetching plan for {station_id}/{date_str}/{hour:02d}: {e}")
                continue

        return {
            "arrivals": all_arrivals,
            "departures": all_departures
        }

    async def search_station(self, query: str) -> List[Dict[str, Any]]:
        """Search for stations in database."""
        results = []
        query_lower = query.lower()

        for name, data in STATIONS_BY_NAME.items():
            if query_lower in name:
                results.append({
                    "id": data["eva"],
                    "name": data["name"],
                    "lat": data["lat"],
                    "lon": data["lon"],
                })
                # Limit results to avoid overwhelming response
                if len(results) >= 50:
                    break

        return results

    async def get_station_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get station by name."""
        return await self.get_station_info(name)
