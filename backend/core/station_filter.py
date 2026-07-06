"""
Filter German ICE/IC long-distance stations from the stations database.

This module provides utilities to filter for German stations that are served
by high-speed (ICE) or intercity (IC) trains.
"""

import json
from pathlib import Path
from typing import TypedDict


class Station(TypedDict):
    """Type definition for a filtered station."""

    eva: str
    name: str
    lat: float
    lon: float
    related_evas: list[str]


# Transport types that indicate long-distance service
LONG_DISTANCE_TRANSPORTS = {"HIGH_SPEED_TRAIN", "INTERCITY_TRAIN"}


def _load_stations_json() -> list[dict]:
    """Load raw stations data from JSON file."""
    stations_file = Path(__file__).parent.parent / "data" / "stations.json"
    with open(stations_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("stations", [])


def _is_german_station(eva: str) -> bool:
    """Check if EVA number indicates a German station (starts with 80)."""
    return eva.startswith("80")


def _is_long_distance_station(available_transports: list[str]) -> bool:
    """Check if station has long-distance train service."""
    return bool(LONG_DISTANCE_TRANSPORTS.intersection(available_transports))


def _filter_station(station: dict) -> Station | None:
    """
    Filter a single station and return Station object if it qualifies.

    Returns None if station doesn't meet criteria.
    """
    eva = str(station.get("eva", ""))
    name = station.get("name", "")
    lat = station.get("lat")
    lon = station.get("lon")
    available_transports = station.get("available_transports", [])
    meta_evas = station.get("meta_evas", [])

    # Skip if missing required fields
    if not eva or not name or lat is None or lon is None:
        return None

    # Filter for German stations only
    if not _is_german_station(eva):
        return None

    # Filter for long-distance stations
    if not _is_long_distance_station(available_transports):
        return None

    return Station(
        eva=eva,
        name=name,
        lat=float(lat),
        lon=float(lon),
        related_evas=[str(e) for e in meta_evas],
    )


# Cache for filtered stations
_cached_stations: list[Station] | None = None
_cached_stations_by_eva: dict[str, Station] | None = None


def get_long_distance_stations() -> list[Station]:
    """
    Get all German long-distance (ICE/IC) stations.

    Returns a list of approximately 354 stations that are:
    - Located in Germany (EVA starts with "80")
    - Served by HIGH_SPEED_TRAIN (ICE) or INTERCITY_TRAIN (IC)

    The result is cached after the first call.
    """
    global _cached_stations, _cached_stations_by_eva

    if _cached_stations is not None:
        return _cached_stations

    raw_stations = _load_stations_json()
    filtered: list[Station] = []
    by_eva: dict[str, Station] = {}

    for raw in raw_stations:
        station = _filter_station(raw)
        if station is not None:
            filtered.append(station)
            by_eva[station["eva"]] = station

    _cached_stations = filtered
    _cached_stations_by_eva = by_eva

    return _cached_stations


def get_station_with_aliases(eva: str) -> tuple[Station | None, list[str]]:
    """
    Get a station and all its related EVA numbers (aliases).

    This handles station fragmentation where one logical station has multiple
    EVA numbers for different platforms/sections (e.g., Berlin Hbf and
    Berlin Hbf S-Bahn).

    Args:
        eva: The EVA number to look up

    Returns:
        A tuple of (station, all_evas) where:
        - station: The Station object if found, None otherwise
        - all_evas: List of all related EVA numbers (including the input EVA
          and any related_evas from the station's meta_evas field)
    """
    global _cached_stations_by_eva

    # Ensure cache is populated
    if _cached_stations_by_eva is None:
        get_long_distance_stations()

    assert _cached_stations_by_eva is not None

    station = _cached_stations_by_eva.get(eva)

    # Build list of all related EVAs
    all_evas: set[str] = {eva}

    if station is not None:
        all_evas.update(station["related_evas"])

    return station, list(all_evas)


if __name__ == "__main__":
    # Quick test/verification
    stations = get_long_distance_stations()
    print(f"Found {len(stations)} German long-distance stations")

    # Show a few examples
    print("\nExample stations:")
    for s in stations[:5]:
        print(f"  {s['eva']}: {s['name']} ({s['lat']}, {s['lon']})")
        if s["related_evas"]:
            print(f"    Related EVAs: {s['related_evas']}")

    # Test get_station_with_aliases
    test_eva = "8000105"  # Frankfurt Hbf
    station, all_evas = get_station_with_aliases(test_eva)
    if station:
        print(f"\nTest get_station_with_aliases('{test_eva}'):")
        print(f"  Station: {station['name']}")
        print(f"  All EVAs: {all_evas}")
