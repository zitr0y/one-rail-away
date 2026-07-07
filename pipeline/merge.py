r"""Cross-feed station merging: collapse the same physical station across national feeds.

The same station appears in several GTFS feeds under different stop_ids, names, and
slightly offset coordinates. `merge_stations` assigns each (feed, stop_id) a canonical
station id, building one `Station` registry shared by the router.

Canonical id precedence (first match wins):
  1. alias override  -- explicit "<feed>:<stop_id>" -> canonical id in `aliases`
  2. UIC regex       -- cfg.uic_regex extracts a UIC code from the stop_id
  3. proximity       -- an already-registered station <500 m away AND with the same
                        normalized name (accent-transliterated, lowercase, alphanumeric
                        only -- see `_norm`)
  4. fresh id        -- "x:<feed>:<stop_id>" (never merges with anything)

The FIRST feed to register a canonical id wins its display name, coordinates, and
country; later feeds only contribute their mapping entry.

Coordinate-less STUBS (RawStop.lat/lon None -- the foreign half of a cross-border
trip, kept by gtfs.load_feed instead of dropped) are resolved in a SECOND pass,
after every real station has settled: an explicit alias wins, else an unambiguous
normalized-name match onto a real station. A stub never creates a canonical
station; unmatched or ambiguous stubs are omitted from the mapping, which the
build stage reads as "strip this stop from its trips".

Determinism (#5): who registers a canonical id first wins its name/coords/country, and
"first" is decided by iteration order. Python dicts preserve insertion order, so this
function is fully deterministic for a given `per_feed` -- the same input always yields
the same registry. Feed order is treated as an intentional PRIORITY signal, not noise:
CALLERS MUST PASS FEEDS IN STABLE, HIGHEST-PRIORITY-FIRST ORDER. The feed that should
own a shared station's display name (e.g. the home-country feed) goes first. We do NOT
sort feed names, because that would silently hand precedence to whichever feed sorts
alphabetically first rather than to the one the caller considers authoritative.

UIC extraction guard (#6): `cfg.uic_regex` is typically `(\d{7})`, and `re.search`
would happily match the first 7 digits of a longer run -- e.g. the real DE IFOPT id
`de:08212:90:1:12345678` (an 8-digit run) would yield a bogus `1234567`. We reject any
match whose captured digits are immediately adjacent to another digit, i.e. we only
accept a run of EXACTLY the matched length. Fixture ids (`st:3333333`, `bs-3333333`)
have a clean 7-digit run bounded by non-digits and still resolve to `3333333`.
"""

import math
import re
import unicodedata

from pipeline.config import FeedConfig
from pipeline.gtfs import RawStop
from pipeline.models import Station

PROXIMITY_M = 500


def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres via an equirectangular approximation.

    Accurate to well under a percent at the sub-kilometre scale we care about
    (station-to-station), which is all the proximity fallback needs.
    """
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return math.hypot(x, y) * 6_371_000


def _norm(name: str) -> str:
    """Normalize a station name for comparison: transliterate accents, lowercase,
    alphanumeric only.

    NFKD-decomposes the name (splitting accented letters into base + combining
    mark), drops the combining marks, lowercases, then strips everything but
    [a-z0-9]. This makes "München Hbf" and "Munchen Hbf" compare equal, so the
    same station spelled with or without diacritics across feeds still
    proximity-merges instead of silently registering as two stations.

    Known limit: German ue/oe/ae digraph spellings ("Muenchen") are NOT
    equivalent to their umlaut form ("München") under this normalization --
    "muenchenhbf" != "munchenhbf". Those variants need an explicit
    station_aliases.toml entry.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", ascii_only.lower())


def _uic_match(uic_re: re.Pattern[str] | None, stop_id: str) -> str | None:
    """Extract a UIC code from stop_id, rejecting matches embedded in a longer digit run.

    Returns the captured group (group 1 if present, else the whole match), or None if
    there is no match or the match is part of a longer run of digits (see module #6).
    """
    if uic_re is None:
        return None
    m = uic_re.search(stop_id)
    if m is None:
        return None
    # Prefer an explicit capture group; fall back to the whole match. If the
    # regex has a group 1 but it didn't participate in this match (e.g. it sits
    # in an unmatched alternation branch), m.group(1) is None and m.start(1)/
    # m.end(1) are both -1 -- guard against that before using them.
    if m.lastindex and m.group(1) is None:
        return None
    start, end = (m.start(1), m.end(1)) if m.lastindex else (m.start(), m.end())
    before = stop_id[start - 1] if start > 0 else ""
    after = stop_id[end] if end < len(stop_id) else ""
    if before.isdigit() or after.isdigit():
        # Match is a substring of a longer digit run -> not a clean UIC code.
        return None
    return m.group(1) if m.lastindex else m.group()


def merge_stations(
    per_feed: dict[str, tuple[list[RawStop], FeedConfig]],
    aliases: dict[str, str],
) -> tuple[list[Station], dict[tuple[str, str], str]]:
    """Merge stops from many feeds into one canonical station registry.

    See module docstring for the id precedence rules and determinism guarantees.

    Returns:
        (stations, mapping) where `stations` is the deduplicated registry and
        `mapping` maps every (feed_name, stop_id) to its canonical station id.
    """
    registry: dict[str, Station] = {}
    mapping: dict[tuple[str, str], str] = {}
    stubs: list[tuple[str, str, str, FeedConfig]] = []  # (feed, stop_id, name, cfg)

    # Pass 1: real (coordinate-bearing) stops. Stubs (lat/lon None) are deferred so
    # they can only resolve ONTO settled real stations, never seed one themselves.
    for feed, (stops, cfg) in per_feed.items():
        uic_re = re.compile(cfg.uic_regex) if cfg.uic_regex else None
        for stop in stops:
            if stop.lat is None or stop.lon is None:
                stubs.append((feed, stop.stop_id, stop.name, cfg))
                continue
            canonical = aliases.get(f"{feed}:{stop.stop_id}")
            if canonical is None:
                canonical = _uic_match(uic_re, stop.stop_id)
            if canonical is None:
                canonical = next(
                    (
                        sid
                        for sid, s in registry.items()
                        if _norm(s.name) == _norm(stop.name)
                        and _dist_m(s.lat, s.lon, stop.lat, stop.lon) < PROXIMITY_M
                    ),
                    None,
                ) or f"x:{feed}:{stop.stop_id}"
            if canonical not in registry:
                registry[canonical] = Station(
                    id=canonical,
                    name=stop.name,
                    lat=stop.lat,
                    lon=stop.lon,
                    country=cfg.country,
                )
            mapping[(feed, stop.stop_id)] = canonical

    # Pass 2: coordinate-less stubs. An explicit alias wins; otherwise resolve by an
    # UNAMBIGUOUS normalized-name match onto a real station. A stub NEVER creates a
    # canonical station -- unmatched or ambiguous stubs are simply left out of the
    # mapping, which the build stage reads as "strip this stop from its trips".
    by_norm: dict[str, list[str]] = {}
    for sid, s in registry.items():
        by_norm.setdefault(_norm(s.name), []).append(sid)
    for feed, stop_id, name, _cfg in stubs:
        alias = aliases.get(f"{feed}:{stop_id}")
        if alias is not None and alias in registry:
            mapping[(feed, stop_id)] = alias
            continue
        candidates = by_norm.get(_norm(name), [])
        if len(candidates) == 1:  # unambiguous
            mapping[(feed, stop_id)] = candidates[0]
        # else: unmatched (0 candidates) or ambiguous (>1) -> dropped

    return list(registry.values()), mapping
