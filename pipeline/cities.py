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
from typing import cast

from pipeline.models import Station, TransferMode

log = logging.getLogger(__name__)

ResolvedTransfer = tuple[str, str, int, TransferMode]

TRANSFER_MODES = {
    "walk",
    "metro",
    "tram",
    "cercanias",
    "rer",
    "train-shuttle",
    "bus",
}


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


def load_transfers(
    path: Path, stations: list[Station]
) -> tuple[list[ResolvedTransfer], list[str]]:
    """Resolve valid configured pairs against an already-merged station list."""
    if not path.exists():
        return [], []

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    table = raw.get("transfers", {})
    city_groups = raw.get("cities", {})

    by_name: dict[str, list[str]] = {}
    for s in stations:
        by_name.setdefault(s.name, []).append(s.id)

    transfers: list[ResolvedTransfer] = []
    warnings: list[str] = []

    def warn(message: str) -> None:
        log.warning(message)
        warnings.append(message)

    for city, entries in table.items():
        for entry in entries:
            if not isinstance(entry, list) or len(entry) != 4:
                warn(f"cities.toml: invalid transfer entry for {city!r}: {entry!r}")
                continue

            a, b, mode, minutes = entry
            if (
                not isinstance(a, str)
                or not isinstance(b, str)
                or not isinstance(mode, str)
                or not isinstance(minutes, int)
                or isinstance(minutes, bool)
                or minutes <= 0
            ):
                warn(f"cities.toml: invalid transfer entry for {city!r}: {entry!r}")
                continue

            if mode not in TRANSFER_MODES:
                warn(f"cities.toml: unsupported transfer mode for {city!r}: {mode!r}")
                continue

            if (
                city not in city_groups
                or a not in city_groups[city]
                or b not in city_groups[city]
            ):
                warn(
                    f"cities.toml: transfer {city!r} pair {a!r} -> {b!r} "
                    "does not share that [cities] group"
                )
                continue

            ids_a = by_name.get(a)
            if not ids_a:
                warn(f"cities.toml: no station matches transfer {city!r} endpoint {a!r}")
                continue
            if len(ids_a) != 1:
                warn(
                    f"cities.toml: transfer {city!r} endpoint {a!r} is ambiguous "
                    "after merge, skipping"
                )
                continue

            ids_b = by_name.get(b)
            if not ids_b:
                warn(f"cities.toml: no station matches transfer {city!r} endpoint {b!r}")
                continue
            if len(ids_b) != 1:
                warn(
                    f"cities.toml: transfer {city!r} endpoint {b!r} is ambiguous "
                    "after merge, skipping"
                )
                continue

            transfers.append(
                (ids_a[0], ids_b[0], minutes * 60, cast(TransferMode, mode))
            )

    return transfers, warnings
