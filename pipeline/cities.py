"""Load cities.toml and resolve member stations into city groups.

Mirrors capitals.py: a curated table lives at repo root, matched by exact
station name during ``ose compute``; unmatched members warn but never fail the
build. Unlike capitals (country -> one station), a city maps to SEVERAL member
stations so the UI can select a city by name and show the UNION of all its
stations' reachable destinations, and treat same-city stations as reachable by
a short "local transit" hop (backlog C3).

Coordinate-clustering was rejected during design (2026-07-13): real same-city
termini share the same distance band as unrelated rural branch-line stops, so a
curated table is the only reliable grouping key.
"""

import logging
import tomllib
from pathlib import Path

from pipeline.models import Station

log = logging.getLogger(__name__)


def load_cities(
    path: Path, stations: list[Station]
) -> tuple[dict[str, list[str]], list[str]]:
    """Return (``{city_name: [member station ids]}``, warning messages).

    Each ``[cities]`` entry maps a display city name to a list of exact member
    station names. Members are matched by exact canonical name. An unmatched
    member, or a city that resolves to fewer than two stations, logs a warning
    and is skipped (never fails the build).
    """
    if not path.exists():
        return {}, []

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    table = raw.get("cities", {})

    by_name: dict[str, list[str]] = {}
    for s in stations:
        by_name.setdefault(s.name, []).append(s.id)

    groups: dict[str, list[str]] = {}
    warnings: list[str] = []
    for city, members in table.items():
        ids: list[str] = []
        for member in members:
            matched = by_name.get(member)
            if matched:
                ids.extend(matched)
            else:
                msg = f"cities.toml: no station matches {city!r} member {member!r}"
                log.warning(msg)
                warnings.append(msg)
        # A "union" needs at least two stations to be meaningful.
        if len(ids) >= 2:
            groups[city] = ids
        elif ids:
            msg = f"cities.toml: city {city!r} resolved to <2 stations, skipping"
            log.warning(msg)
            warnings.append(msg)

    return groups, warnings
