"""
API routes for the train network visualization system.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel

from core.network_service import NetworkService
from core.cache_service import CacheService
from core.models import NetworkData, Connection


router = APIRouter(prefix="/api", tags=["network"])

# Initialize services
network_service = NetworkService()
cache_service = CacheService()


class FetchNetworkRequest(BaseModel):
    """Request model for fetching network data."""
    station_name: str = "Essen Hbf"
    force_refresh: bool = False
    max_connections: Optional[int] = None


class FetchNetworkResponse(BaseModel):
    """Response model for fetch network endpoint."""
    success: bool
    message: str
    data: Optional[NetworkData] = None
    cached: bool = False


class FilterConnectionsRequest(BaseModel):
    """Request model for filtering connections."""
    direct_only: bool = True
    min_speed_kmh: Optional[float] = None
    max_speed_kmh: Optional[float] = None
    train_types: Optional[List[str]] = None


@router.post("/fetch-network", response_model=FetchNetworkResponse)
async def fetch_network(request: FetchNetworkRequest):
    """
    Fetch and cache network data for a station.

    This endpoint will check the cache first and return cached data if available
    and not expired (unless force_refresh is True).
    """
    try:
        # Check cache first
        if not request.force_refresh:
            # We need to get station info to get the ID for cache lookup
            station_info = await network_service.get_station_info(request.station_name)
            if station_info and cache_service.is_cache_valid(station_info.id):
                cached_data = cache_service.load_network_data(station_info.id)
                if cached_data:
                    return FetchNetworkResponse(
                        success=True,
                        message="Network data retrieved from cache",
                        data=cached_data,
                        cached=True
                    )

        # Fetch fresh data
        network_data = await network_service.fetch_network_data(
            station_name=request.station_name,
            max_connections=request.max_connections
        )

        # Cache the data
        cache_service.save_network_data(network_data)

        return FetchNetworkResponse(
            success=True,
            message="Network data fetched successfully",
            data=network_data,
            cached=False
        )

    except ValueError as e:
        print(f"ValueError in fetch_network: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Exception in fetch_network: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching network data: {str(e)}")


@router.get("/network/{station_id}", response_model=NetworkData)
async def get_network(station_id: str):
    """
    Get cached network data for a station by ID.
    """
    network_data = cache_service.load_network_data(station_id)
    if not network_data:
        raise HTTPException(
            status_code=404,
            detail=f"No cached data found for station {station_id}"
        )

    return network_data


@router.get("/stations/cached")
async def list_cached_stations():
    """
    List all stations with cached network data.
    """
    cached_stations = cache_service.list_cached_stations()
    return {
        "total": len(cached_stations),
        "stations": cached_stations
    }


@router.get("/stations/top")
async def get_top_stations(limit: int = Query(default=10, ge=1, le=100)):
    """
    Get top stations by connection count from cached data.
    """
    cached_stations = cache_service.list_cached_stations()

    # Sort by connection count
    sorted_stations = sorted(
        cached_stations,
        key=lambda x: x.get("connection_count", 0),
        reverse=True
    )

    return {
        "total": len(sorted_stations),
        "limit": limit,
        "stations": sorted_stations[:limit]
    }


@router.post("/connections/filter")
async def filter_connections(
    station_id: str,
    filters: FilterConnectionsRequest
):
    """
    Filter connections based on criteria.
    """
    # Load network data
    network_data = cache_service.load_network_data(station_id)
    if not network_data:
        raise HTTPException(
            status_code=404,
            detail=f"No cached data found for station {station_id}"
        )

    # Apply filters
    filtered_connections = network_data.connections

    # Filter by speed
    if filters.min_speed_kmh is not None:
        filtered_connections = [
            c for c in filtered_connections
            if c.aerial_speed_kmh >= filters.min_speed_kmh
        ]

    if filters.max_speed_kmh is not None:
        filtered_connections = [
            c for c in filtered_connections
            if c.aerial_speed_kmh <= filters.max_speed_kmh
        ]

    # Filter by train type
    if filters.train_types:
        filtered_connections = [
            c for c in filtered_connections
            if c.train_type in filters.train_types
        ]

    return {
        "station_id": station_id,
        "station_name": network_data.origin_station.name,
        "total_connections": len(network_data.connections),
        "filtered_connections": len(filtered_connections),
        "connections": filtered_connections
    }


@router.delete("/cache/{station_id}")
async def clear_station_cache(station_id: str):
    """
    Clear cached data for a specific station.
    """
    cache_service.clear_cache(station_id)
    return {
        "success": True,
        "message": f"Cache cleared for station {station_id}"
    }


@router.delete("/cache")
async def clear_all_cache():
    """
    Clear all cached network data.
    """
    cache_service.clear_cache()
    return {
        "success": True,
        "message": "All cache cleared"
    }
