"""
Service for reading pre-computed connection data.
"""

import json
from datetime import datetime
from pathlib import Path

from core.models import (
    PrecomputedNetworkData,
    StationSummary,
)


class PrecomputedService:
    """Service for reading pre-computed connection data."""

    def __init__(self, data_dir: Path | None = None):
        """
        Initialize the precomputed service.

        Args:
            data_dir: Path to the precomputed data directory.
                     Defaults to backend/data/precomputed/
        """
        if data_dir is None:
            # Default to backend/data/precomputed/
            self.data_dir = Path(__file__).parent.parent / "data" / "precomputed"
        else:
            self.data_dir = data_dir

    def _load_index(self) -> dict | None:
        """
        Load the index.json file.

        Returns:
            Index data dict or None if file doesn't exist
        """
        index_path = self.data_dir / "index.json"
        if not index_path.exists():
            return None

        try:
            with open(index_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def list_available_stations(self) -> list[StationSummary]:
        """
        List all stations with pre-computed data from index.json.

        Returns:
            List of StationSummary objects for all available stations
        """
        index_data = self._load_index()
        if not index_data:
            return []

        stations_by_eva: dict[str, StationSummary] = {}
        for station_data in index_data.get("stations", []):
            try:
                eva = station_data["eva"]
                # Skip duplicates (keep first occurrence)
                if eva in stations_by_eva:
                    continue
                summary = StationSummary(
                    eva=eva,
                    name=station_data["name"],
                    lat=station_data["lat"],
                    lon=station_data["lon"],
                    connection_count=station_data.get("connection_count", 0),
                )
                stations_by_eva[eva] = summary
            except (KeyError, ValueError):
                # Skip malformed entries
                continue

        return list(stations_by_eva.values())

    def get_station_connections(self, station_id: str) -> PrecomputedNetworkData | None:
        """
        Load pre-computed connections for a station from connections_{eva}.json.

        Args:
            station_id: The station EVA ID

        Returns:
            PrecomputedNetworkData or None if not found
        """
        connections_path = self.data_dir / f"connections_{station_id}.json"
        if not connections_path.exists():
            return None

        try:
            with open(connections_path, encoding="utf-8") as f:
                data = json.load(f)

            return PrecomputedNetworkData(**data)
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    def get_last_compute_time(self) -> datetime | None:
        """
        When was data last pre-computed (from index.json).

        Returns:
            datetime of last computation or None if unknown
        """
        index_data = self._load_index()
        if not index_data:
            return None

        computed_at = index_data.get("computed_at")
        if not computed_at:
            return None

        try:
            # Handle ISO format with or without Z suffix
            if computed_at.endswith("Z"):
                computed_at = computed_at[:-1]
            return datetime.fromisoformat(computed_at)
        except ValueError:
            return None
