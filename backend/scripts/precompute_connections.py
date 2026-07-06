#!/usr/bin/env python3
"""
Pre-computation script for train connections.

Computes all direct train connections for German ICE/IC stations and saves
the results to JSON files for fast lookup by the API.

Usage:
    python backend/scripts/precompute_connections.py
"""

import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from geopy.distance import geodesic

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config  # noqa: E402
from core.db_api_client import (  # noqa: E402
    DBAPIClient,
    STATIONS_BY_NAME,
    get_all_related_evas,
)
from core.station_filter import get_long_distance_stations, Station  # noqa: E402


# Output directory for precomputed data
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "precomputed"

# Maximum parallel API calls to avoid rate limiting
MAX_PARALLEL_REQUESTS = 10


def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate straight-line (aerial) distance between two points in km."""
    if not all([lat1, lon1, lat2, lon2]):
        return 0.0
    try:
        return geodesic((lat1, lon1), (lat2, lon2)).kilometers
    except Exception:
        return 0.0


class ConnectionPrecomputer:
    """Precomputes train connections for all ICE/IC stations."""

    def __init__(self):
        """Initialize the precomputer."""
        self.api_client = DBAPIClient()
        self.stations = get_long_distance_stations()
        self.stations_by_eva = {s["eva"]: s for s in self.stations}
        self.semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
        self.index_data: list[dict] = []
        # In-memory cache for station plan data (arrivals/departures)
        # Key: (eva, date_str), Value: plan dict
        self._plan_cache: dict[tuple[str, str], dict] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    async def fetch_departures_for_station(
        self, station: Station
    ) -> tuple[list[dict], list[str]]:
        """
        Fetch all departures from a station and its related EVAs.

        Args:
            station: The station to fetch departures for

        Returns:
            Tuple of (departures list, list of EVAs fetched from)
        """
        eva = station["eva"]
        related_evas = station.get("related_evas", [])

        # Include the main EVA and all related EVAs
        # Filter to only German EVAs (start with "80") that the DB API supports
        all_evas = [eva] + [e for e in related_evas if e != eva and e.startswith("80")]

        all_departures = []
        fetched_evas = []

        for current_eva in all_evas:
            try:
                async with self.semaphore:
                    departures = await self.api_client.get_departures(current_eva)
                    all_departures.extend(departures)
                    fetched_evas.append(current_eva)
            except Exception as e:
                print(f"    Error fetching EVA {current_eva}: {e}")

        # Deduplicate departures by (train_number, time, destination)
        seen = set()
        unique_departures = []
        for dep in all_departures:
            key = (dep.get("number"), dep.get("time"), dep.get("destination"))
            if key not in seen:
                seen.add(key)
                unique_departures.append(dep)

        return unique_departures, fetched_evas

    async def fetch_arrivals_for_destination(
        self, dest_eva: str, date_str: str
    ) -> dict:
        """
        Fetch arrival data for a destination station, using cache if available.

        Args:
            dest_eva: Destination EVA number
            date_str: Date in YYMMDD format

        Returns:
            Dict with 'arrivals' list
        """
        # Check cache first
        cache_key = (dest_eva, date_str)
        if cache_key in self._plan_cache:
            self._cache_hits += 1
            return self._plan_cache[cache_key]

        self._cache_misses += 1

        # Get all related EVAs for the destination
        related_evas = get_all_related_evas(dest_eva)

        all_arrivals = []

        # Fetch from current hour through next 12 hours
        current_hour = datetime.now().hour
        hours_to_fetch = [(current_hour + i) % 24 for i in range(13)]

        for eva in related_evas:
            # Check if we have this related EVA cached
            related_cache_key = (eva, date_str)
            if related_cache_key in self._plan_cache:
                all_arrivals.extend(
                    self._plan_cache[related_cache_key].get("arrivals", [])
                )
                continue

            try:
                async with self.semaphore:
                    plan_data = await self.api_client.get_full_plan(
                        eva, date_str, hours_to_fetch
                    )
                    # Cache the individual EVA's plan data
                    self._plan_cache[related_cache_key] = plan_data
                    all_arrivals.extend(plan_data.get("arrivals", []))
            except Exception:
                # Silently skip errors for individual EVAs
                pass

        # Cache the aggregated result for this destination
        result = {"arrivals": all_arrivals}
        self._plan_cache[cache_key] = result
        return result

    def find_arrival_time(
        self,
        arrivals: list[dict],
        train_number: str,
        departure_time: datetime,
    ) -> Optional[datetime]:
        """
        Find the arrival time for a specific train.

        Args:
            arrivals: List of arrival records
            train_number: Train number to match
            departure_time: Departure time from origin

        Returns:
            Arrival datetime if found, None otherwise
        """
        for arrival in arrivals:
            if arrival.get("number") == train_number:
                time_str = arrival.get("time", "")
                if len(time_str) == 10:
                    try:
                        arrival_dt = datetime.strptime(time_str, "%y%m%d%H%M")
                        # Sanity check: arrival should be after departure
                        time_diff = (arrival_dt - departure_time).total_seconds() / 60
                        # Valid range: 1 minute to 24 hours
                        if 1 <= time_diff <= 1440:
                            return arrival_dt
                    except ValueError:
                        continue
        return None

    def filter_long_distance_departures(self, departures: list[dict]) -> list[dict]:
        """
        Filter departures to only include ICE/IC trains.

        Args:
            departures: List of all departures

        Returns:
            Filtered list with only ICE/IC trains
        """
        long_distance_types = {"ICE", "IC", "EC", "ECE", "TGV", "RJ", "RJX", "NJ"}
        return [
            dep
            for dep in departures
            if dep.get("type", "").upper() in long_distance_types
        ]

    async def compute_connections_for_station(
        self, station: Station, station_index: int, total_stations: int
    ) -> Optional[dict]:
        """
        Compute all connections for a single station.

        Args:
            station: Station to compute connections for
            station_index: Current station index (1-based)
            total_stations: Total number of stations

        Returns:
            Connection data dict or None if error
        """
        eva = station["eva"]
        name = station["name"]
        lat = station["lat"]
        lon = station["lon"]

        print(f"[{station_index}/{total_stations}] Processing {name} ({eva})...")

        try:
            # Fetch all departures
            departures, fetched_evas = await self.fetch_departures_for_station(station)

            if len(fetched_evas) > 1:
                print(f"    Fetched from {len(fetched_evas)} related EVAs")

            # Filter to long-distance trains only
            departures = self.filter_long_distance_departures(departures)
            print(f"    Found {len(departures)} ICE/IC departures")

            if not departures:
                return {
                    "station": {"eva": eva, "name": name, "lat": lat, "lon": lon},
                    "computed_at": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "connections": [],
                    "statistics": {"total_destinations": 0, "avg_speed_kmh": 0},
                }

            # Extract unique destinations that are ICE/IC stations
            date_str = datetime.now().strftime("%y%m%d")
            destinations_to_fetch: set[str] = set()

            for dep in departures:
                path_stations = dep.get("path_stations", [])
                for dest_name in path_stations:
                    station_info = STATIONS_BY_NAME.get(dest_name.lower())
                    if station_info:
                        dest_eva = station_info.get("eva")
                        # Only include if it's an ICE/IC station
                        if dest_eva and dest_eva in self.stations_by_eva:
                            destinations_to_fetch.add(dest_eva)

            print(f"    {len(destinations_to_fetch)} destination ICE/IC stations found")

            # Fetch arrival data for all destinations in parallel
            dest_plans: dict[str, dict] = {}

            async def fetch_dest(dest_eva: str):
                plan = await self.fetch_arrivals_for_destination(dest_eva, date_str)
                return dest_eva, plan

            tasks = [fetch_dest(d) for d in destinations_to_fetch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, tuple):
                    dest_eva, plan = result
                    dest_plans[dest_eva] = plan

            print(f"    Fetched arrival data for {len(dest_plans)} destinations")

            # Build connections
            connections: list[dict] = []
            seen_pairs: set[tuple] = set()
            train_counts: Counter = Counter()  # Count trains per destination

            for dep in departures:
                train_number = dep.get("number", "")
                train_type = dep.get("type", "")
                time_str = dep.get("time", "")

                if len(time_str) != 10:
                    continue

                try:
                    departure_dt = datetime.strptime(time_str, "%y%m%d%H%M")
                except ValueError:
                    continue

                path_stations = dep.get("path_stations", [])

                for dest_name in path_stations:
                    station_info = STATIONS_BY_NAME.get(dest_name.lower())
                    if not station_info:
                        continue

                    dest_eva = station_info.get("eva")
                    if not dest_eva or dest_eva not in self.stations_by_eva:
                        continue

                    # Skip if we've already processed this train-destination pair
                    pair_key = (train_number, dest_eva)
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # Skip if we don't have arrival data
                    if dest_eva not in dest_plans:
                        continue

                    # Find arrival time
                    arrival_dt = self.find_arrival_time(
                        dest_plans[dest_eva].get("arrivals", []),
                        train_number,
                        departure_dt,
                    )

                    if not arrival_dt:
                        continue

                    # Get destination station info
                    dest_station = self.stations_by_eva.get(dest_eva)
                    if not dest_station:
                        continue

                    dest_lat = dest_station["lat"]
                    dest_lon = dest_station["lon"]

                    # Calculate distance and travel time
                    distance_km = _calculate_distance(lat, lon, dest_lat, dest_lon)
                    if distance_km <= 0:
                        continue

                    travel_time_minutes = int(
                        (arrival_dt - departure_dt).total_seconds() / 60
                    )
                    if travel_time_minutes <= 0:
                        continue

                    aerial_speed_kmh = round(
                        (distance_km / travel_time_minutes) * 60, 2
                    )

                    # Track train count for daily frequency
                    train_counts[dest_eva] += 1

                    connection = {
                        "destination_id": dest_eva,
                        "destination_name": dest_station["name"],
                        "destination_lat": dest_lat,
                        "destination_lon": dest_lon,
                        "train_type": train_type,
                        "train_number": train_number,
                        "departure_time": departure_dt.strftime("%H:%M"),
                        "arrival_time": arrival_dt.strftime("%H:%M"),
                        "travel_time_minutes": travel_time_minutes,
                        "distance_km": round(distance_km, 2),
                        "aerial_speed_kmh": aerial_speed_kmh,
                    }
                    connections.append(connection)

            # Add daily frequency to connections
            for conn in connections:
                conn["daily_frequency"] = train_counts[conn["destination_id"]]

            # Calculate statistics
            unique_destinations = len(set(c["destination_id"] for c in connections))
            avg_speed = 0.0
            if connections:
                avg_speed = round(
                    sum(c["aerial_speed_kmh"] for c in connections) / len(connections),
                    2,
                )

            print(
                f"    Created {len(connections)} connections to "
                f"{unique_destinations} destinations (avg speed: {avg_speed} km/h)"
            )

            return {
                "station": {"eva": eva, "name": name, "lat": lat, "lon": lon},
                "computed_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "connections": connections,
                "statistics": {
                    "total_destinations": unique_destinations,
                    "avg_speed_kmh": avg_speed,
                },
            }

        except Exception as e:
            print(f"    ERROR: {e}")
            return None

    async def run(self):
        """Run the precomputation for all stations."""
        print(f"\n{'=' * 60}")
        print("TRAIN CONNECTION PRE-COMPUTATION")
        print(f"{'=' * 60}")
        print(f"Stations to process: {len(self.stations)}")
        print(f"Output directory: {OUTPUT_DIR}")
        print(f"Max parallel requests: {MAX_PARALLEL_REQUESTS}")
        print(f"{'=' * 60}\n")

        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Process each station
        total = len(self.stations)
        successful = 0
        failed = 0

        for idx, station in enumerate(self.stations, 1):
            result = await self.compute_connections_for_station(station, idx, total)

            if result:
                # Save to file
                output_file = OUTPUT_DIR / f"connections_{station['eva']}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                # Add to index
                self.index_data.append(
                    {
                        "eva": station["eva"],
                        "name": station["name"],
                        "lat": station["lat"],
                        "lon": station["lon"],
                        "connection_count": result["statistics"]["total_destinations"],
                    }
                )
                successful += 1
            else:
                failed += 1

            # Small delay to be nice to the API
            await asyncio.sleep(0.1)

        # Save index file
        index = {
            "computed_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "stations": self.index_data,
        }
        index_file = OUTPUT_DIR / "index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        # Calculate cache effectiveness
        total_cache_requests = self._cache_hits + self._cache_misses
        cache_hit_rate = (
            (self._cache_hits / total_cache_requests * 100)
            if total_cache_requests > 0
            else 0
        )

        print(f"\n{'=' * 60}")
        print("PRECOMPUTATION COMPLETE")
        print(f"{'=' * 60}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Cache hits: {self._cache_hits}")
        print(f"Cache misses: {self._cache_misses}")
        print(f"Cache hit rate: {cache_hit_rate:.1f}%")
        print(f"Index file: {index_file}")
        print(f"{'=' * 60}\n")


async def main():
    """Main entry point."""
    # Validate config
    if not config.DB_API_KEY or not config.DB_CLIENT_ID:
        print("ERROR: DB_API_KEY and DB_CLIENT_ID must be set in .env file")
        sys.exit(1)

    precomputer = ConnectionPrecomputer()
    await precomputer.run()


if __name__ == "__main__":
    asyncio.run(main())
