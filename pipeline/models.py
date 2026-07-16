from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TransferMode = Literal[
    "walk", "metro", "tram", "cercanias", "rer", "train-shuttle", "bus"
]


class CountryOverride(BaseModel):
    name: str
    lat: float
    lon: float
    country: str


class Station(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    country: str
    has_reach: bool = False
    n_dest: int = 0
    n_routes: int = 0
    is_capital: bool = False


class StopTime(BaseModel):
    station: str
    arr: int  # minutes since midnight of sample date
    dep: int


class Trip(BaseModel):
    trip_id: str
    train: str  # display name, e.g. "ICE 517"
    stops: list[StopTime]
    # Feed provenance survives through-routing so sampled availability can
    # distinguish an absent service from a date the upstream feed cannot cover.
    feeds: list[str] = Field(default_factory=list)


class Leg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    train: str
    dep: str  # "HH:MM"
    arr: str
    from_: str = Field(alias="from")
    to: str
    via: list[str]  # station ids strictly between from and to
    feeds: list[str] = Field(default_factory=list, exclude=True)


class TransferLeg(BaseModel):
    type: Literal["transfer"] = "transfer"
    mode: TransferMode
    minutes: int
    from_id: str
    to_id: str


JourneyLeg = Leg | TransferLeg


class Journey(BaseModel):
    trains: int
    duration_min: int
    legs: list[JourneyLeg]


class Destination(BaseModel):
    id: str
    direct_per_day: int
    journeys: list[Journey]  # ascending trains; each strictly faster than previous
    frequency: "Frequency | None" = None


class Frequency(BaseModel):
    """Evidence from the finite set of sampled service dates.

    ``weekly_direct_estimate`` is deliberately rounded and only an estimate;
    the dates are sparse probes, not a complete calendar read.
    """

    # ``sample_days`` is the number of probes for which this route had feed
    # coverage. ``requested_sample_days`` keeps the sampling provenance visible.
    requested_sample_days: int
    sample_days: int
    available_days: int
    direct_days: int
    direct_trips: int
    direct_per_active_day: float | None = None
    weekly_direct_estimate: int | None = None
    availability: Literal["year_round", "limited", "coverage_limited"]
    active_months: list[str]


class ReachFile(BaseModel):
    origin: str
    computed_at: str
    sample_date: str
    destinations: list[Destination]
