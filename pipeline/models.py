from pydantic import BaseModel, ConfigDict, Field


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


class Leg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    train: str
    dep: str  # "HH:MM"
    arr: str
    from_: str = Field(alias="from")
    to: str
    via: list[str]  # station ids strictly between from and to


class Journey(BaseModel):
    trains: int
    duration_min: int
    legs: list[Leg]


class Destination(BaseModel):
    id: str
    direct_per_day: int
    journeys: list[Journey]  # ascending trains; each strictly faster than previous


class ReachFile(BaseModel):
    origin: str
    computed_at: str
    sample_date: str
    destinations: list[Destination]
