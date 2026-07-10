import tomllib
from pathlib import Path

from pydantic import BaseModel, model_validator


class FeedConfig(BaseModel):
    url: str
    country: str
    license: str
    route_allow: list[str]  # regexes matched against route short/long name
    # Optional trip-level filter: regexes matched against trips.txt
    # trip_short_name. When set, a trip is kept only if its route passes
    # route_allow AND its trip_short_name matches one of these, and the
    # trip_short_name becomes the train display label. Needed for feeds whose
    # route names carry no train category (OEBB: corridor codes like "A10-1",
    # with the real category "RJ 658" living in trip_short_name).
    trip_allow: list[str] | None = None
    # Optional stop-id-level trip filter: regexes matched against the stop_ids a
    # trip serves; a trip is kept only if at least one of its stop ids matches.
    # Needed for feeds where the commercial brand lives only in per-brand stop
    # ids (SNCF combined export: "StopPoint:OCETGV INOUI-87686006" vs
    # "StopPoint:OCETrain TER-...", with no brand in route or trip fields).
    stop_id_allow: list[str] | None = None
    # Optional stop-id brand table: regex pattern -> brand word. When set, the
    # patterns act as the stop-id trip filter (same semantics as stop_id_allow)
    # AND each kept trip is relabeled "<brand> <trip_headsign>". Needed for the
    # SNCF combined export: the commercial brand lives only in per-brand stop
    # ids and the train number only in trip_headsign (route_short_name is an
    # opaque line code like "802A").
    stop_id_brand: dict[str, str] | None = None
    uic_regex: str | None = None  # extracts UIC code from stop_id

    @model_validator(mode="after")
    def _single_stop_id_filter(self) -> "FeedConfig":
        if self.stop_id_allow and self.stop_id_brand:
            raise ValueError("set stop_id_allow or stop_id_brand, not both")
        return self


def load_feeds(path: Path) -> dict[str, FeedConfig]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return {name: FeedConfig(**cfg) for name, cfg in raw.get("feeds", {}).items()}
