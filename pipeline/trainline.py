"""Match our stations to Trainline location ids (booking handoff, backlog N).

Source: https://github.com/trainline-eu/stations (`stations.csv`, `;`-separated,
ODbL-1.0). Only the id is used: `/api/book` turns a pair of ids into a
Trainline search-results URL.
"""

import csv
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

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


def normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())


def load_candidates(path: Path) -> list[Candidate]:
    """Searchable Trainline stations with coordinates; [] if the file is missing."""
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            if row.get("is_suggestable") != "t" or not row.get("latitude") or not row.get("longitude"):
                continue
            out.append(Candidate(row["id"], row["name"], float(row["latitude"]), float(row["longitude"])))
    return out


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dx = (lon2 - lon1) * 111.32 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 110.57
    return math.hypot(dx, dy)


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return (math.floor(lat / _CELL), math.floor(lon / _CELL))


def _names_match(ours: str, theirs: str) -> bool:
    if ours == theirs:
        return True
    if min(len(ours), len(theirs)) < MIN_CONTAINS_LEN:
        return False
    return ours in theirs or theirs in ours


def match_stations(
    stations: list[tuple[str, str, float, float]], candidates: list[Candidate]
) -> dict[str, str]:
    """{our id: trainline id} for `(id, name, lat, lon)` stations that match."""
    grid: dict[tuple[int, int], list[Candidate]] = defaultdict(list)
    for c in candidates:
        grid[_cell(c.lat, c.lon)].append(c)
    normalized = {c.id: normalize_name(c.name) for c in candidates}

    ids: dict[str, str] = {}
    for sid, name, lat, lon in stations:
        if "(Gr)" in name:
            continue
        ci, cj = _cell(lat, lon)
        nearby = sorted(
            ((_km(lat, lon, c.lat, c.lon), c)
             for di in (-1, 0, 1) for dj in (-2, -1, 0, 1, 2) for c in grid[(ci + di, cj + dj)]),
            key=lambda t: t[0],
        )
        ours = normalize_name(name)
        named = [c for d, c in nearby if d <= NAME_RADIUS_KM and _names_match(ours, normalized[c.id])]
        if named:
            ids[sid] = named[0].id
        elif nearby and nearby[0][0] <= COORD_RADIUS_KM:
            ids[sid] = nearby[0][1].id
    return ids
