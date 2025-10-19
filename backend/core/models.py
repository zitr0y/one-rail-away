"""
Data models for the train network visualization system.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field


class Station(BaseModel):
    """Represents a train station with geographic coordinates."""
    id: str = Field(..., description="Station ID from DB API")
    name: str = Field(..., description="Station name")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    connection_count: int = Field(default=0, description="Number of connections from this station")


class RouteWaypoint(BaseModel):
    """A waypoint along a train route."""
    station_name: str = Field(..., description="Station name")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    arrival_time: Optional[datetime] = Field(None, description="Estimated arrival time")
    distance_from_origin_km: float = Field(0.0, description="Cumulative distance from origin")


class Connection(BaseModel):
    """Represents a train connection between two stations, potentially via intermediate stops."""
    origin_id: str = Field(..., description="Origin station ID")
    origin_name: str = Field(..., description="Origin station name")
    destination_id: str = Field(..., description="Destination station ID")
    destination_name: str = Field(..., description="Destination station name")
    destination_lat: float = Field(..., description="Destination latitude")
    destination_lon: float = Field(..., description="Destination longitude")

    # Train information
    train_type: str = Field(..., description="Type of train (ICE, IC, RE, etc.)")
    train_number: Optional[str] = Field(None, description="Train number/line")

    # Timing information
    departure_time: datetime = Field(..., description="Scheduled departure time")
    arrival_time: datetime = Field(..., description="Scheduled arrival time")
    travel_time_minutes: int = Field(..., description="Travel time in minutes")

    # Geographic and speed data
    distance_km: float = Field(..., description="Straight-line distance in kilometers")
    aerial_speed_kmh: float = Field(..., description="Aerial speed (distance / time) in km/h")

    # Route path (intermediate stations)
    route_waypoints: List[RouteWaypoint] = Field(
        default_factory=list,
        description="Intermediate stations along the route from origin to destination"
    )

    # Additional metadata
    platform: Optional[str] = Field(None, description="Departure platform")
    delay: Optional[int] = Field(None, description="Delay in minutes")
    is_real_time: bool = Field(
        default=False,
        description="Whether arrival_time is from real API data (True) or estimated (False)"
    )
    path_station_names: List[str] = Field(
        default_factory=list,
        description="Raw list of station names in the train's path (for rebuilding waypoints)"
    )


class NetworkData(BaseModel):
    """Represents the complete network data for a station."""
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When data was fetched")
    origin_station: Station = Field(..., description="The origin station")
    connections: List[Connection] = Field(default_factory=list, description="List of all direct connections")
    multi_hop_routes: List[MultiHopRoute] = Field(default_factory=list, description="List of multi-hop routes")

    # Statistics
    total_connections: int = Field(default=0, description="Total number of direct connections")
    total_multi_hop_routes: int = Field(default=0, description="Total number of multi-hop routes")
    average_speed_kmh: float = Field(default=0.0, description="Average aerial speed")
    max_speed_kmh: float = Field(default=0.0, description="Maximum aerial speed")
    max_distance_km: float = Field(default=0.0, description="Maximum distance")

    def calculate_statistics(self) -> None:
        """Calculate statistics from connections."""
        if not self.connections:
            return

        self.total_connections = len(self.connections)
        self.total_multi_hop_routes = len(self.multi_hop_routes)
        speeds = [c.aerial_speed_kmh for c in self.connections]
        distances = [c.distance_km for c in self.connections]

        self.average_speed_kmh = sum(speeds) / len(speeds) if speeds else 0.0
        self.max_speed_kmh = max(speeds) if speeds else 0.0
        self.max_distance_km = max(distances) if distances else 0.0


class ConnectionLeg(BaseModel):
    """A single leg/segment of a multi-hop journey."""
    origin_id: str = Field(..., description="Origin station ID for this leg")
    origin_name: str = Field(..., description="Origin station name for this leg")
    destination_id: str = Field(..., description="Destination station ID for this leg")
    destination_name: str = Field(..., description="Destination station name for this leg")

    # Train information
    train_type: str = Field(..., description="Type of train (ICE, IC, RE, etc.)")
    train_number: Optional[str] = Field(None, description="Train number/line")

    # Timing information
    departure_time: datetime = Field(..., description="Departure time for this leg")
    arrival_time: datetime = Field(..., description="Arrival time for this leg")
    travel_time_minutes: int = Field(..., description="Travel time for this leg in minutes")

    # Geographic data
    distance_km: float = Field(..., description="Distance for this leg in kilometers")
    aerial_speed_kmh: float = Field(..., description="Aerial speed for this leg in km/h")

    # Additional metadata
    platform: Optional[str] = Field(None, description="Departure platform")


class TransferInfo(BaseModel):
    """Information about a transfer/changeover between legs."""
    station_id: str = Field(..., description="Station where transfer occurs")
    station_name: str = Field(..., description="Station name")
    station_lat: float = Field(..., description="Station latitude")
    station_lon: float = Field(..., description="Station longitude")
    arrival_time: datetime = Field(..., description="Arrival time of incoming leg")
    departure_time: datetime = Field(..., description="Departure time of outgoing leg")
    waiting_time_minutes: int = Field(..., description="Waiting time at this station in minutes")
    arrival_platform: Optional[str] = Field(None, description="Arrival platform")
    departure_platform: Optional[str] = Field(None, description="Departure platform")


class MultiHopRoute(BaseModel):
    """A complete journey consisting of multiple connection legs with changeovers."""
    origin_id: str = Field(..., description="Overall journey origin station ID")
    origin_name: str = Field(..., description="Overall journey origin station name")
    destination_id: str = Field(..., description="Overall journey destination station ID")
    destination_name: str = Field(..., description="Overall journey destination station name")
    destination_lat: float = Field(..., description="Final destination latitude")
    destination_lon: float = Field(..., description="Final destination longitude")

    # Journey legs and transfers
    legs: List[ConnectionLeg] = Field(..., description="List of connection legs in order")
    transfers: List[TransferInfo] = Field(default_factory=list, description="List of transfers/changeovers")

    # Overall journey metrics
    total_travel_time_minutes: int = Field(..., description="Total journey time including transfers")
    total_distance_km: float = Field(..., description="Total distance across all legs")
    total_waiting_time_minutes: int = Field(default=0, description="Total waiting time at all transfers")
    number_of_changeovers: int = Field(..., description="Number of changeovers/transfers")
    average_aerial_speed_kmh: float = Field(..., description="Average aerial speed across entire journey")

    # Timing
    departure_time: datetime = Field(..., description="Overall journey start time")
    arrival_time: datetime = Field(..., description="Overall journey end time")

    # Metadata
    is_real_time: bool = Field(default=True, description="Whether all legs use real API data")


class StationSummary(BaseModel):
    """Summary information about a station for the top stations list."""
    station: Station
    unique_destinations: int = Field(..., description="Number of unique destination stations")
    total_daily_connections: int = Field(..., description="Total number of connections per day")
