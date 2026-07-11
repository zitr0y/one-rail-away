"""Load capitals.toml and resolve against a station list."""

import logging
import tomllib
from pathlib import Path

from pipeline.models import Station

log = logging.getLogger(__name__)


def load_capitals(
    path: Path, stations: list[Station]
) -> tuple[set[str], list[str]]:
    """Return (set of capital station ids, list of warning messages).

    Each ``[capitals]`` entry is matched by exact name AND country.
    Unmatched entries produce a warning but never fail the build.
    """
    if not path.exists():
        return set(), []

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    table = raw.get("capitals", {})

    by_country_name: dict[tuple[str, str], str] = {}
    for s in stations:
        by_country_name[(s.country, s.name)] = s.id

    capital_ids: set[str] = set()
    warnings: list[str] = []
    for country, name in table.items():
        key = (country.upper(), name)
        sid = by_country_name.get(key)
        if sid:
            capital_ids.add(sid)
        else:
            msg = f"capitals.toml: no station matches {country}={name!r}"
            log.warning(msg)
            warnings.append(msg)

    return capital_ids, warnings
