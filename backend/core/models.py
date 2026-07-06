"""
Data models for the train network visualization system.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TrainCategory(str, Enum):
    """Train category classification."""

    REGIONAL = "regional"  # S-Bahn, RB, RE, etc.
    INTERCITY = "intercity"  # IC, ICE, Eurostar, NJ, etc.
    OTHER = "other"  # Everything else


# Regional train types (valid for Deutschland-Ticket)
REGIONAL_TRAIN_TYPES = {
    "S",
    "RB",
    "RE",
    "IRE",
    "MEX",
    "ALX",
    "BOB",
    "BRB",
    "MRB",
    "ERB",
    "ABR",
    "VBG",
    "SBB",
    "STB",
    "VEN",
    "VIA",
    "ZUG",
}


# Inter-city train types (NOT valid for Deutschland-Ticket)
INTERCITY_TRAIN_TYPES = {
    "IC",
    "ICE",
    "EC",
    "EN",
    "CNL",
    "NJ",
    "RJ",
    "TGV",
    "EST",
    "THA",
    "RJX",
    "FLX",
    "ECE",
    "D",
    "WB",
}


def classify_train_type(train_type: str) -> TrainCategory:
    """
    Classify a train type into a category.

    Args:
        train_type: The train type string (e.g., "ICE", "RE", "S")

    Returns:
        TrainCategory enum value
    """
    train_type_upper = train_type.upper().strip()

    if train_type_upper in REGIONAL_TRAIN_TYPES:
        return TrainCategory.REGIONAL
    elif train_type_upper in INTERCITY_TRAIN_TYPES:
        return TrainCategory.INTERCITY
    else:
        return TrainCategory.OTHER


class StationSummary(BaseModel):
    """Summary information about a station for listing available pre-computed stations."""

    eva: str = Field(..., description="Station EVA ID")
    name: str = Field(..., description="Station name")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    connection_count: int = Field(
        default=0, description="Number of unique destinations"
    )


class PrecomputedConnection(BaseModel):
    """A pre-computed connection from one station to another."""

    destination_id: str = Field(..., description="Destination station EVA ID")
    destination_name: str = Field(..., description="Destination station name")
    destination_lat: float = Field(..., description="Destination latitude")
    destination_lon: float = Field(..., description="Destination longitude")
    train_type: str = Field(..., description="Type of train (ICE, IC, etc.)")
    train_number: str = Field(..., description="Train number")
    departure_time: str = Field(..., description="Departure time (HH:MM)")
    arrival_time: str = Field(..., description="Arrival time (HH:MM)")
    travel_time_minutes: int = Field(..., description="Travel time in minutes")
    distance_km: float = Field(..., description="Straight-line distance in km")
    aerial_speed_kmh: float = Field(..., description="Aerial speed in km/h")
    daily_frequency: int = Field(
        default=1, description="Number of trains per day to this destination"
    )


class PrecomputedStationInfo(BaseModel):
    """Station information in pre-computed data."""

    eva: str = Field(..., description="Station EVA ID")
    name: str = Field(..., description="Station name")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")


class PrecomputedStatistics(BaseModel):
    """Statistics for pre-computed connection data."""

    total_destinations: int = Field(
        default=0, description="Number of unique destinations"
    )
    avg_speed_kmh: float = Field(
        default=0.0, description="Average aerial speed in km/h"
    )


class PrecomputedNetworkData(BaseModel):
    """Pre-computed network data for a station."""

    station: PrecomputedStationInfo = Field(..., description="Origin station info")
    computed_at: str = Field(..., description="ISO timestamp when data was computed")
    connections: list[PrecomputedConnection] = Field(
        default_factory=list, description="List of connections"
    )
    statistics: PrecomputedStatistics = Field(
        default_factory=PrecomputedStatistics, description="Connection statistics"
    )
