"""Match our stations to Trainline location ids (booking handoff, backlog N).

Source: https://github.com/trainline-eu/stations (`stations.csv`, `;`-separated,
ODbL-1.0). Only the id is used: `/api/book` turns a pair of ids into a
Trainline search-results URL.
"""

import csv
import logging
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

NAME_RADIUS_KM = 5.0
COORD_RADIUS_KM = 0.5
MIN_CONTAINS_LEN = 4
_CELL = 0.1  # degrees; +-1 cell north-south and +-2 east-west covers >= 5 km up to ~70°N


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    lat: float
    lon: float


# Letters NFKD leaves whole (so `encode("ascii", "ignore")` would drop them):
# "Główny" must fold to "glowny", not "gowny".
_FOLD = str.maketrans({
    "ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ß": "ss",
    "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ı": "i",
})


def normalize_name(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name.translate(_FOLD))
    ascii_name = folded.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())


def load_candidates(path: Path) -> list[Candidate]:
    """Searchable Trainline stations with coordinates; [] if the file is missing
    or unparsable (booking then falls back to the homepage; compute carries on)."""
    if not path.exists():
        return []
    out = []
    try:
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                lat, lon = row.get("latitude"), row.get("longitude")
                if row.get("is_suggestable") != "t" or not lat or not lon:
                    continue
                out.append(Candidate(row["id"], row["name"], float(lat), float(lon)))
    except (ValueError, KeyError, UnicodeDecodeError, csv.Error) as exc:
        log.warning("trainline: cannot parse %s (%r); no candidates", path, exc)
        return []
    return out


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dx = (lon2 - lon1) * 111.32 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 110.57
    return math.hypot(dx, dy)


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return (math.floor(lat / _CELL), math.floor(lon / _CELL))


def _contains(ours: str, theirs: str) -> bool:
    if min(len(ours), len(theirs)) < MIN_CONTAINS_LEN:
        return False
    return ours in theirs or theirs in ours


def match_stations(
    stations: list[tuple[str, str, float, float]],
    candidates: list[Candidate],
    stats: dict[str, int] | None = None,
) -> dict[str, str]:
    """{our id: trainline id} for `(id, name, lat, lon)` stations that match.

    Within 5 km an exact normalised name beats containment, nearest first in
    each tier; failing both, the nearest candidate within 500 m. If `stats` is
    given it receives counts: `name`, `coord` matches and skipped `border` points.
    """
    counts = {"name": 0, "coord": 0, "border": 0}
    grid: dict[tuple[int, int], list[Candidate]] = defaultdict(list)
    for c in candidates:
        grid[_cell(c.lat, c.lon)].append(c)
    normalized = {c.id: normalize_name(c.name) for c in candidates}

    ids: dict[str, str] = {}
    for sid, name, lat, lon in stations:
        if "(Gr)" in name:
            counts["border"] += 1
            continue
        ci, cj = _cell(lat, lon)
        nearby = sorted(
            ((_km(lat, lon, c.lat, c.lon), c)
             for di in (-1, 0, 1) for dj in (-2, -1, 0, 1, 2) for c in grid[(ci + di, cj + dj)]),
            key=lambda t: t[0],
        )
        ours = normalize_name(name)
        close = [c for d, c in nearby if d <= NAME_RADIUS_KM]
        named = [c for c in close if normalized[c.id] == ours] or [
            c for c in close if _contains(ours, normalized[c.id])
        ]
        if named:
            ids[sid] = named[0].id
            counts["name"] += 1
        elif nearby and nearby[0][0] <= COORD_RADIUS_KM:
            ids[sid] = nearby[0][1].id
            counts["coord"] += 1
    if stats is not None:
        stats.update(counts)
    return ids
