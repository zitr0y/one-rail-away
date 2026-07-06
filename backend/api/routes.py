"""
API routes for the train network visualization system.
"""

from fastapi import APIRouter, HTTPException, Query

from core.models import (
    StationSummary,
    PrecomputedNetworkData,
)
from core.db_api_client import STATIONS_BY_NAME
from core.precomputed_service import PrecomputedService


router = APIRouter(prefix="/api", tags=["network"])

# Initialize services
precomputed_service = PrecomputedService()


@router.get("/stations/search")
async def search_stations(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
):
    """
    Search for stations by name (autocomplete).

    Returns stations matching the query string, sorted by relevance.
    """
    query_lower = q.lower()

    # Search through all stations
    matches = []

    for name, station_data in STATIONS_BY_NAME.items():
        # Check if query matches station name
        if query_lower in name:
            # Calculate relevance score (exact match at start is best)
            if name.startswith(query_lower):
                score = 1000 - len(name)  # Shorter names with exact match rank higher
            else:
                score = 500 - len(name)

            matches.append(
                {
                    "id": station_data["eva"],
                    "name": station_data["name"],
                    "lat": station_data["lat"],
                    "lon": station_data["lon"],
                    "score": score,
                }
            )

    # Sort by score (descending) and limit results
    matches.sort(key=lambda x: x["score"], reverse=True)
    results = matches[:limit]

    # Remove score from results
    for result in results:
        del result["score"]

    return {
        "query": q,
        "total_results": len(matches),
        "returned_results": len(results),
        "stations": results,
    }


# =============================================================================
# Pre-computed data endpoints
# =============================================================================


@router.get("/stations/available")
async def list_available_stations():
    """
    List all pre-computed stations for the frontend dropdown.

    Returns a list of all stations that have pre-computed connection data available.
    """
    stations = precomputed_service.list_available_stations()
    return {
        "stations": [s.model_dump() for s in stations],
        "total": len(stations),
    }


@router.get("/connections/{station_id}", response_model=PrecomputedNetworkData)
async def get_station_connections(station_id: str):
    """
    Get pre-computed connections for a station.

    Args:
        station_id: The station EVA ID

    Returns:
        Pre-computed network data for the station

    Raises:
        HTTPException 404: If no pre-computed data exists for the station
    """
    connections = precomputed_service.get_station_connections(station_id)
    if connections is None:
        raise HTTPException(
            status_code=404,
            detail=f"No pre-computed data found for station {station_id}",
        )
    return connections


@router.get("/precompute/status")
async def get_precompute_status():
    """
    Check when data was last computed.

    Returns information about the pre-computed data status.
    """
    last_compute_time = precomputed_service.get_last_compute_time()
    available_stations = precomputed_service.list_available_stations()

    return {
        "last_computed_at": last_compute_time.isoformat()
        if last_compute_time
        else None,
        "total_stations": len(available_stations),
        "data_available": len(available_stations) > 0,
    }
