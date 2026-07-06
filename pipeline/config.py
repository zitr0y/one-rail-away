import tomllib
from pathlib import Path

from pydantic import BaseModel


class FeedConfig(BaseModel):
    url: str
    country: str
    license: str
    route_allow: list[str]  # regexes matched against route display name
    uic_regex: str | None = None  # extracts UIC code from stop_id


def load_feeds(path: Path) -> dict[str, FeedConfig]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return {name: FeedConfig(**cfg) for name, cfg in raw.get("feeds", {}).items()}
