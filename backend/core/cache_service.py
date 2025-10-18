"""
Service for caching network data to disk.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from config import config
from core.models import NetworkData


class CacheService:
    """Service for caching and retrieving network data."""

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize cache service.

        Args:
            data_dir: Directory for storing cached data
        """
        self.data_dir = data_dir or config.DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, station_id: str) -> Path:
        """
        Get cache file path for a station.

        Args:
            station_id: Station ID

        Returns:
            Path to cache file
        """
        # Sanitize station ID for filename
        safe_id = "".join(c if c.isalnum() else "_" for c in station_id)
        return self.data_dir / f"network_{safe_id}.json"

    def save_network_data(self, network_data: NetworkData) -> None:
        """
        Save network data to cache.

        Args:
            network_data: NetworkData to cache
        """
        cache_path = self._get_cache_path(network_data.origin_station.id)

        # Convert to dict for JSON serialization
        data_dict = network_data.model_dump(mode='json')

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data_dict, f, indent=2, ensure_ascii=False, default=str)

    def load_network_data(self, station_id: str) -> Optional[NetworkData]:
        """
        Load network data from cache.

        Args:
            station_id: Station ID

        Returns:
            NetworkData if found, None otherwise
        """
        cache_path = self._get_cache_path(station_id)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data_dict = json.load(f)

            return NetworkData(**data_dict)
        except Exception as e:
            print(f"Error loading cache for station {station_id}: {e}")
            return None

    def is_cache_valid(
        self,
        station_id: str,
        max_age_hours: int = 24
    ) -> bool:
        """
        Check if cached data is still valid.

        Args:
            station_id: Station ID
            max_age_hours: Maximum age of cache in hours

        Returns:
            True if cache exists and is fresh
        """
        network_data = self.load_network_data(station_id)
        if not network_data:
            return False

        # Check if data is too old
        age = datetime.utcnow() - network_data.timestamp
        return age < timedelta(hours=max_age_hours)

    def list_cached_stations(self) -> list[dict]:
        """
        List all cached stations.

        Returns:
            List of dicts with station info and cache metadata
        """
        cached_stations = []

        for cache_file in self.data_dir.glob("network_*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                origin = data.get("origin_station", {})
                timestamp = data.get("timestamp")

                cached_stations.append({
                    "station_id": origin.get("id"),
                    "station_name": origin.get("name"),
                    "connection_count": data.get("total_connections", 0),
                    "cached_at": timestamp,
                    "file_path": str(cache_file)
                })
            except Exception as e:
                print(f"Error reading cache file {cache_file}: {e}")
                continue

        return cached_stations

    def clear_cache(self, station_id: Optional[str] = None) -> None:
        """
        Clear cached data.

        Args:
            station_id: If provided, clear only this station. Otherwise clear all.
        """
        if station_id:
            cache_path = self._get_cache_path(station_id)
            if cache_path.exists():
                cache_path.unlink()
        else:
            # Clear all cache files
            for cache_file in self.data_dir.glob("network_*.json"):
                cache_file.unlink()
