"""Join border-split through-services back into single trips.

European GTFS feeds model an international train as SEPARATE trips per country
segment (2026-07 build evidence: RJX 134 appears as "Venezia Santa Lucia ->
Tarvisio" plus "Tarvisio -> Klagenfurt"; the Wien->Budapest railjets split at
Hegyeshalom; EC 95 Berlin->Warszawa splits at Rzepin). Left unjoined, a direct
train counts as 2+ "trains" in the reachability output and vanishes from the
map's "1 train" view beyond the border stop.

Join rules — all must hold, deliberately conservative because train labels are
LINE labels shared by every run of the line and by both directions:
- both trips carry the same label and the label contains a digit ("RJX 134");
  unnumbered labels ("EC", "RJ") are too ambiguous to join. Caveat: labels are
  only unique per feed by convention — in the 2026-07 build SNCF ICE numbers
  (95xx) happen to be disjoint from db_fern ICE numbers, and a future refresh
  where the ranges overlap would silently join unrelated cross-feed trips if
  the other rules line up,
- trip A ends at the exact canonical station where trip B starts,
- B departs 0..MAX_GAP_MIN minutes after A arrives (border dwell: loco/crew
  change),
- no station revisit: the joined path never visits a station twice, which
  rejects out+return pairs meeting at a terminus,
- the pairing is unambiguous: equal-gap ties for the same predecessor or
  successor are skipped with a warning.

Passes repeat until stable so 3+ segment chains collapse fully.
"""

import logging
import re

from pipeline.models import StopTime, Trip

logger = logging.getLogger(__name__)

# Longest border dwell observed among real candidate pairs in the 2026-07 build
# was ~45 min (median 25); 60 keeps headroom without inviting false joins.
MAX_GAP_MIN = 60
_MAX_PASSES = 5


def _candidates(trips: list[Trip]) -> list[tuple[int, int, int]]:
    """Every joinable (gap, index_a, index_b), sorted so iteration is deterministic
    and smallest gaps are matched first."""
    by_label: dict[str, list[int]] = {}
    for i, t in enumerate(trips):
        if re.search(r"\d", t.train):
            by_label.setdefault(t.train, []).append(i)
    out: list[tuple[int, int, int]] = []
    for idxs in by_label.values():
        for i in idxs:
            a = trips[i]
            for j in idxs:
                if i == j:
                    continue
                b = trips[j]
                if a.stops[-1].station != b.stops[0].station:
                    continue
                gap = b.stops[0].dep - a.stops[-1].arr
                if not 0 <= gap <= MAX_GAP_MIN:
                    continue
                if {s.station for s in a.stops[:-1]} & {s.station for s in b.stops[1:]}:
                    continue
                out.append((gap, i, j))
    return sorted(out)


def _ambiguous(cands: list[tuple[int, int, int]], trips: list[Trip]) -> set[tuple[int, int]]:
    """Pairs that tie at the same gap for the same predecessor or successor."""
    skip: set[tuple[int, int]] = set()
    for k, (gap, i, j) in enumerate(cands):
        for gap2, i2, j2 in cands[k + 1 :]:
            if gap2 != gap:
                break
            if i2 == i or j2 == j:
                skip.add((i, j))
                skip.add((i2, j2))
                logger.warning(
                    "ambiguous through-join for %s at %s (gap %d min): skipping",
                    trips[i].train,
                    trips[i].stops[-1].station,
                    gap,
                )
    return skip


def join_through_services(trips: list[Trip]) -> list[Trip]:
    """Return a new trip list with border-split segments joined. Inputs unmutated."""
    trips = list(trips)
    total = 0
    for _ in range(_MAX_PASSES):
        cands = _candidates(trips)
        skip = _ambiguous(cands, trips)
        touched: set[int] = set()
        absorbed: set[int] = set()
        for _gap, i, j in cands:
            if (i, j) in skip or i in touched or j in touched:
                continue
            a, b = trips[i], trips[j]
            boundary = StopTime(
                station=a.stops[-1].station, arr=a.stops[-1].arr, dep=b.stops[0].dep
            )
            trips[i] = Trip(
                trip_id=f"{a.trip_id}+{b.trip_id}",
                train=a.train,
                stops=[*a.stops[:-1], boundary, *b.stops[1:]],
                feeds=list(dict.fromkeys([*a.feeds, *b.feeds])),
            )
            touched.update((i, j))
            absorbed.add(j)
            total += 1
        if not absorbed:
            break
        trips = [t for k, t in enumerate(trips) if k not in absorbed]
    else:
        logger.warning("through-join did not stabilize after %d passes", _MAX_PASSES)
    if total:
        logger.info("joined %d border-split trip segments", total)
    return trips
