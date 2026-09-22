r"""Cross-feed station merging: collapse the same physical station across national feeds.

The same station appears in several GTFS feeds under different stop_ids, names, and
slightly offset coordinates. `merge_stations` assigns each (feed, stop_id) a canonical
station id, building one `Station` registry shared by the router.

Canonical id precedence (first match wins):
  1. alias override  -- explicit "<feed>:<stop_id>" or "<feed>@<stop name>" ->
                        canonical id or "<feed>@<stop name>" reference in `aliases`
  2. UIC regex       -- cfg.uic_regex extracts a UIC code from the stop_id; a
                        known code merges onto its station, an UNKNOWN code first
                        falls back to the rule-3 proximity check (#7)
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

UIC fallback (#7, 2026-07-10): a UIC-extracted stop used to become canonical
immediately, so it could never proximity-merge onto a station already registered
under a non-UIC id (every sncf StopArea:OCE.../db_fern internal id) -- each
collision needed a manual station_aliases.toml entry (Konstanz, Mulhouse,
Frasne). Now an unknown code first runs the same proximity+name check as rule 3;
on a hit the code is recorded in a run-local uic_aliases map so every later feed
carrying the same code lands on the same station regardless of its coordinates
or spelling, and on a miss the code is minted as canonical exactly as before.
The fallback may merge onto a DIFFERENT UIC canonical (dual-code border
stations; symmetric with rule 3 -- user decision 2026-07-10). Cross-language
name twins ("Sarrebruck" vs "Saarbruecken Hbf") do not normalize equal and
still need explicit aliases.

Name-keyed references (2026-09-22): db_fern stop ids rotate with EVERY export,
so an alias written against them breaks on the next refresh (it aborted the
weekly build for two months) or silently mints a ghost twin under the dead
id. "<feed>@<stop name>" names a stop by its normalized (`_norm`) name
instead, as a key (which stops the alias applies to) or as a target (the
canonical station that feed's stop landed on; the feed must be processed
first). A reference that matches nothing, or a target that matches several
stations, is reported through ``issues`` and never aborts: an unresolved
target falls through to rules 2-4, an ambiguous one takes the first match.
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


_STROKE_MAP = str.maketrans({
    "ł": "l", "Ł": "L",
    "ø": "o", "Ø": "O",
    "đ": "d", "Đ": "D",
    "œ": "oe", "Œ": "Oe",
    "æ": "ae", "Æ": "Ae",
})


def _norm(name: str) -> str:
    """Normalize a station name for comparison: transliterate accents, lowercase,
    alphanumeric only.

    NFKD-decomposes the name (splitting accented letters into base + combining
    mark), drops the combining marks, lowercases, then strips everything but
    [a-z0-9]. This makes "München Hbf" and "Munchen Hbf" compare equal, so the
    same station spelled with or without diacritics across feeds still
    proximity-merges instead of silently registering as two stations.

    German station-word equivalence (driven by real cross-feed pairs <50 m apart
    in the 2026-07 build): the leading S-Bahn/U-Bahn marker "S+U " (db_fern
    parent stations) is dropped, "hauptbahnhof" collapses to "hbf" (db_fern "Hbf"
    vs oebb "Hauptbahnhof"), and ONE trailing "bahnhof" is stripped (oebb
    "Rosenheim Bahnhof" vs db_fern "Rosenheim", ns "München Ost" vs oebb
    "München Ostbahnhof"). The <500 m proximity requirement still guards against
    merging distinct stations that happen to normalize alike.

    Known limit: German ue/oe/ae digraph spellings ("Muenchen") are NOT
    equivalent to their umlaut form ("München") under this normalization --
    "muenchenhbf" != "munchenhbf". Those variants need an explicit
    station_aliases.toml entry.

    Unlike German ue/oe/ae digraphs, stroke letters (ł/Ł, ø/Ø, đ/Đ, œ/Œ, æ/Æ)
    do not decompose under NFKD and are mapped explicitly beforehand.
    This is safe because proximity merging is guarded by the <500 m distance rule.
    """
    if name.lower().startswith("s+u "):
        name = name[4:]
    name = name.translate(_STROKE_MAP)
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    collapsed = re.sub(r"[^a-z0-9]", "", ascii_only.lower())
    collapsed = collapsed.replace("hauptbahnhof", "hbf")
    return re.sub(r"(?<=.)bahnhof$", "", collapsed)


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


def _proximity_match(
    registry: dict[str, Station],
    by_norm: dict[str, list[str]],
    name: str,
    lat: float,
    lon: float,
) -> str | None:
    """First registered station <PROXIMITY_M away whose name normalizes equal.

    ``by_norm`` contains station ids in registry insertion order, retaining the
    documented feed-priority tie-break while avoiding a full registry scan for
    every stop.
    """
    norm = _norm(name)
    return next(
        (
            sid
            for sid in by_norm.get(norm, [])
            if _dist_m(registry[sid].lat, registry[sid].lon, lat, lon) < PROXIMITY_M
        ),
        None,
    )


def _name_ref(ref: str) -> tuple[str, str] | None:
    """Split a "<feed>@<stop name>" reference into (feed, normalized name).

    None for id forms: "<feed>:<stop_id>" keys and plain canonical ids. A feed
    name never contains ':', so an '@' inside a stop id cannot misparse.
    """
    feed, sep, name = ref.partition("@")
    if not sep or not feed or not name or ":" in feed:
        return None
    return feed, _norm(name.partition("~")[0])


HINT_M = 2000


def _near_hint(ref: str, hits: list[str], coords) -> list[str]:
    """Keep only hits within HINT_M of an optional "~lat,lon" suffix on ``ref``.

    Context-free names ("Hauptbahnhof") need the hint: without it a second
    same-named stop elsewhere would be matched silently once the intended one
    is renamed. ``coords(canonical)`` returns (lat, lon).
    """
    hint = ref.partition("~")[2]
    if not hint:
        return hits
    lat, lon = (float(v) for v in hint.split(","))
    return [h for h in hits if _dist_m(lat, lon, *coords(h)) < HINT_M]


def merge_stations(
    per_feed: dict[str, tuple[list[RawStop], FeedConfig]],
    aliases: dict[str, str],
    issues: list[str] | None = None,
) -> tuple[list[Station], dict[tuple[str, str], str]]:
    """Merge stops from many feeds into one canonical station registry.

    See module docstring for the id precedence rules and determinism guarantees.
    Unresolvable name-keyed references are appended to ``issues`` (if given).

    Returns:
        (stations, mapping) where `stations` is the deduplicated registry and
        `mapping` maps every (feed_name, stop_id) to its canonical station id.
    """
    registry: dict[str, Station] = {}
    # Lists preserve the registry's insertion order, which is the intentional
    # feed-priority tie-break for equal-name proximity matches.
    by_norm: dict[str, list[str]] = {}
    mapping: dict[tuple[str, str], str] = {}
    stubs: list[tuple[str, str, str, FeedConfig]] = []  # (feed, stop_id, name, cfg)
    uic_aliases: dict[str, str] = {}  # UIC code -> canonical, from fallback merges (#7)
    done_feeds: set[str] = set()  # feeds fully processed -> their x: ids are settled
    found: list[str] = []
    # Keys match by name alone; a "~lat,lon" hint on a key is not supported.
    name_aliases = {ref: target for key, target in aliases.items() if (ref := _name_ref(key))}
    used_name_keys: set[tuple[str, str]] = set()
    # (feed, normalized stop name) -> canonicals its stops landed on, in order.
    canon_by_name: dict[tuple[str, str], list[str]] = {}

    def alias_for(feed: str, stop_id: str, name: str) -> str | None:
        target = aliases.get(f"{feed}:{stop_id}")
        if target is None:
            key = (feed, _norm(name))
            target = name_aliases.get(key)
            if target is not None:
                used_name_keys.add(key)
        if target is None or (ref := _name_ref(target)) is None:
            return target
        hits = _near_hint(
            target, canon_by_name.get(ref, []), lambda h: (registry[h].lat, registry[h].lon)
        )
        if not hits:
            found.append(f"alias target {target!r} (for {feed}:{stop_id}) matches no stop")
            return None
        if len(hits) > 1:
            found.append(
                f"alias target {target!r} (for {feed}:{stop_id}) is ambiguous: "
                + ", ".join(hits)
            )
        return hits[0]

    # Pass 1: real (coordinate-bearing) stops. Stubs (lat/lon None) are deferred so
    # they can only resolve ONTO settled real stations, never seed one themselves.
    for feed, (stops, cfg) in per_feed.items():
        uic_re = re.compile(cfg.uic_regex) if cfg.uic_regex else None
        for stop in stops:
            if stop.lat is None or stop.lon is None:
                stubs.append((feed, stop.stop_id, stop.name, cfg))
                continue
            canonical = alias_for(feed, stop.stop_id, stop.name)
            if canonical is not None and canonical not in registry:
                # Alias targets embed volatile feed ids (x:db_fern:<id> churns
                # on every DB export). When the target's own feed has already
                # been fully processed and the id never registered, the alias
                # is provably stale: prefer a co-located same-name station over
                # minting a ghost under the dead id (2026-07-17: 32 doubled
                # Polish stations aborted the build). Non-x: targets and
                # forward references to later feeds keep the alias verbatim --
                # an explicit override must still beat proximity (rule 1).
                target_feed = re.match(r"x:([^:]+):", canonical)
                if target_feed is not None and target_feed.group(1) in done_feeds:
                    near = _proximity_match(registry, by_norm, stop.name, stop.lat, stop.lon)
                    if near is not None:
                        canonical = near
            if canonical is None:
                code = _uic_match(uic_re, stop.stop_id)
                if code is not None:
                    if code in registry or code in uic_aliases:
                        canonical = uic_aliases.get(code, code)
                    else:
                        # Unknown code: run the same proximity+name check as
                        # rule 3 before minting it as canonical (#7).
                        near = _proximity_match(registry, by_norm, stop.name, stop.lat, stop.lon)
                        if near is not None:
                            uic_aliases[code] = near
                        canonical = near or code
            if canonical is None:
                canonical = (
                    _proximity_match(registry, by_norm, stop.name, stop.lat, stop.lon)
                    or f"x:{feed}:{stop.stop_id}"
                )
            if canonical not in registry:
                registry[canonical] = Station(
                    id=canonical,
                    name=stop.name,
                    lat=stop.lat,
                    lon=stop.lon,
                    country=cfg.country,
                )
                by_norm.setdefault(_norm(stop.name), []).append(canonical)
            mapping[(feed, stop.stop_id)] = canonical
            hits = canon_by_name.setdefault((feed, _norm(stop.name)), [])
            if canonical not in hits:
                hits.append(canonical)
        done_feeds.add(feed)

    # Pass 2: coordinate-less stubs. An explicit alias wins; otherwise resolve by an
    # UNAMBIGUOUS normalized-name match onto a real station. A stub NEVER creates a
    # canonical station -- unmatched or ambiguous stubs are simply left out of the
    # mapping, which the build stage reads as "strip this stop from its trips".
    by_norm: dict[str, list[str]] = {}
    for sid, s in registry.items():
        by_norm.setdefault(_norm(s.name), []).append(sid)
    for feed, stop_id, name, _cfg in stubs:
        alias = alias_for(feed, stop_id, name)
        if alias is not None and alias in registry:
            mapping[(feed, stop_id)] = alias
            continue
        candidates = by_norm.get(_norm(name), [])
        if len(candidates) == 1:  # unambiguous
            mapping[(feed, stop_id)] = candidates[0]
        # else: unmatched (0 candidates) or ambiguous (>1) -> dropped

    for key in aliases:
        ref = _name_ref(key)
        if ref is not None and ref not in used_name_keys:
            found.append(f"alias key {key!r} matches no stop")
    if issues is not None:
        issues.extend(dict.fromkeys(found))
    return list(registry.values()), mapping
