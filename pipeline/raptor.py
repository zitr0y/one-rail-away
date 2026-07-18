"""RAPTOR-style reachability core.

Answers: which stations can you reach from an origin using <= max_trains trains,
and how fast. For each destination we report the best journey per train-count tier
(ascending `trains`, each strictly faster than the previous; non-improving tiers
omitted). Duration = arrival - actual first departure, minimized over hourly
departure floors 05:00-20:00.

All times are minutes since midnight of the sample date and MAY exceed 1440
(post-midnight arrivals). Arithmetic never wraps; only `fmt` wraps for display.
"""

from bisect import bisect_left
from typing import NamedTuple

from pipeline.cities import ResolvedTransfer
from pipeline.models import Journey, Leg, TransferLeg, Trip

INF = 10**9


def fmt(minutes: int) -> str:
    """Format minutes-since-midnight as 'HH:MM', wrapping the hour modulo 24."""
    return f"{minutes // 60 % 24:02d}:{minutes % 60:02d}"


_INDEX_CACHE: dict[int, tuple[list, list, dict[str, list[int]]]] = {}


class Parent(NamedTuple):
    trip: Trip
    previous_station: str
    board_station: str
    board_dep: int
    alight_arr: int
    board_idx: int
    alight_idx: int
    footpath: ResolvedTransfer | None


class DepartureEvidence(NamedTuple):
    departure_min: int
    direct: bool


def _index(trips):
    """Per-day scan index, built once and reused across every departure floor and
    every origin: the same `trips` list object is handed to us 16 times per
    origin, and again for each of the ~1800 origins in a run.

    Returns (trip_stops, by_station):
      trip_stops[ti] - trip ti's stops as plain (station, arr, dep) tuples.
                       Attribute access on the pydantic Stop models dominated the
                       inner loop; tuple unpacking does not.
      by_station[st] - ascending indices of the trips calling at station `st`.

    Keyed by id(trips), but the entry holds the list itself, so that id cannot be
    recycled onto a different object while the entry is alive.
    """
    hit = _INDEX_CACHE.get(id(trips))
    if hit is not None and hit[0] is trips:
        return hit[1], hit[2]
    trip_stops = [[(s.station, s.arr, s.dep) for s in t.stops] for t in trips]
    by_station: dict[str, list[int]] = {}
    for ti, stops in enumerate(trip_stops):
        for station, _, _ in stops:
            lst = by_station.get(station)
            if lst is None:
                by_station[station] = [ti]
            elif lst[-1] != ti:  # a trip calling twice at one station is listed once
                lst.append(ti)
    _INDEX_CACHE[id(trips)] = (trips, trip_stops, by_station)
    return trip_stops, by_station


def compute_departure_evidence(
    trips: list[Trip],
    origin: str,
    max_trains: int = 3,
    transfer_min: int = 10,
    footpaths: list[ResolvedTransfer] | None = None,
) -> dict[str, list[DepartureEvidence]]:
    """One entry per distinct first train departure that can reach each destination."""
    trip_stops, by_station = _index(trips)
    records: dict[tuple[int, int], dict[str, bool]] = {}

    for ti in by_station.get(origin, ()):
        stops = trip_stops[ti]
        board_idx = next(i for i, (station, _, _) in enumerate(stops) if station == origin)
        label = (ti, board_idx)
        departure_min = stops[board_idx][2]
        reached: dict[str, bool] = {}
        prev: dict[str, int] = {}

        for station, arrival, _ in stops[board_idx + 1 :]:
            if station == origin:
                continue
            if arrival < prev.get(station, INF):
                prev[station] = arrival
            reached[station] = True

        for _ in range(2, max_trains + 1):
            ready = {
                station: arrival + transfer_min for station, arrival in prev.items()
            }
            for a, b, seconds, _mode in footpaths or []:
                for source, target in ((a, b), (b, a)):
                    if source not in prev:
                        continue
                    candidate = prev[source] + seconds // 60
                    if candidate < ready.get(target, INF):
                        ready[target] = candidate

            candidates: set[int] = set()
            for station in ready:
                hits = by_station.get(station)
                if hits:
                    candidates.update(hits)

            cur = dict(prev)
            new_arrival = False
            for next_ti in sorted(candidates):
                board = False
                for station, arrival, departure in trip_stops[next_ti]:
                    if board:
                        if arrival < cur.get(station, INF):
                            cur[station] = arrival
                            if station != origin:
                                reached.setdefault(station, False)
                            new_arrival = True
                    elif ready.get(station, INF) <= departure:
                        board = True

            if not new_arrival:
                break
            prev = cur

        records[label] = reached

    out: dict[str, list[DepartureEvidence]] = {}
    for (ti, board_idx), reached in records.items():
        departure_min = trip_stops[ti][board_idx][2]
        for destination, direct in reached.items():
            out.setdefault(destination, []).append(DepartureEvidence(departure_min, direct))
    return out


def _raptor(trips, origin, dep_floor, max_trains, transfer_min, footpaths):
    """Round k = earliest arrival using <= k trains, departing origin no earlier
    than dep_floor.

    parent[(k, station)] records the train used to reach a station. Board/alight
    indices are indices into trip.stops and are used by `_build_legs` to slice
    the via list.

    Only trips calling at a station reached in round k-1 are scanned. A trip
    touching no such station fails the boarding test at every stop, so it can
    never write: skipping it is exact, not an approximation. Candidates are
    walked in ascending trip index -- the order a full scan would have used --
    because `cur` is read back as it is written within a round, so scan order
    decides which trip wins an equal-arrival tie, and hence which route we show.
    """
    trip_stops, by_station = _index(trips)
    arr: list[dict[str, int]] = [{origin: dep_floor}]
    parent: dict[tuple[int, str], Parent] = {}
    n_trips = len(trips)
    for k in range(1, max_trains + 1):
        prev = arr[k - 1]
        cur = dict(prev)
        # Carry parent pointers forward so a station reached with fewer trains
        # can still be reconstructed at a later round (true leg count < k).
        for st in prev:
            if (k - 1, st) in parent:
                parent[(k, st)] = parent[(k - 1, st)]

        ready: dict[str, tuple[int, str, ResolvedTransfer | None]] = {
            station: (
                arrival + (0 if station == origin else transfer_min),
                station,
                None,
            )
            for station, arrival in prev.items()
        }
        if k > 1:
            for a, b, seconds, mode in footpaths:
                for source, target in ((a, b), (b, a)):
                    if (k - 1, source) not in parent:
                        continue
                    candidate = prev.get(source, INF) + seconds // 60
                    existing = ready.get(target)
                    if existing is None or candidate < existing[0]:
                        ready[target] = (
                            candidate,
                            source,
                            (source, target, seconds, mode),
                        )

        # Only trips calling somewhere we are ready to board can ever be scanned.
        candidates: set[int] = set()
        for st in ready:
            hits = by_station.get(st)
            if hits:
                candidates.update(hits)
        scan = range(n_trips) if len(candidates) == n_trips else sorted(candidates)

        ready_get, cur_get = (
            lambda station: ready.get(station, (INF, "", None))[0],
            cur.get,
        )
        for ti in scan:
            board = None  # (station, dep, idx, previous_station, footpath)
            for i, (station, s_arr, s_dep) in enumerate(trip_stops[ti]):
                if board is not None:
                    if s_arr < cur_get(station, INF):
                        cur[station] = s_arr
                        parent[(k, station)] = Parent(
                            trips[ti], board[3], board[0], board[1], s_arr,
                            board[2], i, board[4],
                        )
                # Consider boarding here if we are not already aboard AND we were
                # ready to board here early enough to make the departure.
                # Mid-route boarding is allowed: this runs at every stop, not just
                # the first.
                elif ready_get(station) <= s_dep:
                    _, previous_station, footpath = ready[station]
                    board = (station, s_dep, i, previous_station, footpath)
        arr.append(cur)
    return arr, parent


def _walk(parent, k, dest, origin):
    """Walk parent pointers back to the origin, allocation-free (no Leg/Journey
    objects, just dict lookups and tuple unpacking).

    Returns (trains, first_dep_minutes) or None if the chain is broken/short.
    `trains` is the true leg count (may be < k: a station reached with fewer
    trains still carries its parent pointer forward, see `_raptor`). The last
    pointer walked (deepest in the loop, since we walk dest->origin) is the
    first leg; its board_dep is the true origin departure -- recovered
    unwrapped from the parent chain rather than re-parsing a wrapped "HH:MM"
    string, so duration stays exact for post-midnight departures.
    """
    st, kk = dest, k
    trains = 0
    first_dep = None
    while st != origin:
        p = parent.get((kk, st))
        if p is None:
            return None
        first_dep = p.board_dep
        st, kk = p.previous_station, kk - 1
        trains += 1
        if kk < 0:
            return None
    return trains, first_dep


def _build_legs(parent, k, dest, origin, display_offsets):
    """Walk parent pointers back to the origin, materializing `Leg` objects.

    Only called once a candidate is already known to win its (dest, trains)
    tier (see `compute_reachability`), so the earlier allocation-free `_walk`
    is not wasted work for the many candidates that don't. Legs are ordered
    origin-first; each leg's `to` equals the next leg's boarding station; via
    lists exclude the two endpoints. Assumes the chain is valid -- callers
    must have already confirmed this via `_walk`.

    `display_offsets` converts the shared reference clock back to each
    station's local wall clock for the dep/arr strings (rail convention:
    every printed time is local to its station).
    """
    off = display_offsets.get
    legs: list[Leg | TransferLeg] = []
    st, kk = dest, k
    while st != origin:
        p = parent[(kk, st)]
        legs.append(
            Leg(
                train=p.trip.train,
                dep=fmt(p.board_dep + off(p.board_station, 0)),
                arr=fmt(p.alight_arr + off(st, 0)),
                **{"from": p.board_station},
                to=st,
                via=[x.station for x in p.trip.stops[p.board_idx + 1 : p.alight_idx]],
                feeds=p.trip.feeds,
            )
        )
        if p.footpath is not None:
            from_id, to_id, seconds, mode = p.footpath
            legs.append(
                TransferLeg(
                    mode=mode,
                    minutes=seconds // 60,
                    from_id=from_id,
                    to_id=to_id,
                )
            )
        # Step back to the station we boarded this leg at, one fewer train.
        st, kk = p.previous_station, kk - 1
    legs.reverse()
    return legs


def compute_reachability(
    trips: list[Trip],
    origin: str,
    max_trains: int = 3,
    transfer_min: int = 10,
    footpaths: list[ResolvedTransfer] | None = None,
    display_offsets: dict[str, int] | None = None,
) -> dict[str, list[Journey]]:
    """Best journey per (destination, train-count) tier, minimized over hourly
    departure floors 05:00-20:00 LOCAL to the origin, then collapsed to
    strictly-improving tiers.

    Trip times arrive on one shared reference clock (see gtfs.REF_TZ);
    `display_offsets` maps station id -> minutes from that clock to the
    station's local clock (absent = 0). It shifts the floor window to origin
    wall time and localizes the dep/arr strings on materialized legs; all
    arithmetic stays on the reference clock, so durations are exact.

    Floors are deduplicated first. `dep_floor` reaches the search in exactly one
    way: a trip is boardable at the origin iff its departure there is >= the
    floor (the origin's own buffer is 0, and every other station starts at INF).
    The origin's entry in `arr` stays pinned at `dep_floor` in every round -- you
    cannot arrive back at the origin earlier than you left it -- so the floor
    changes nothing else, and `dest == origin` is skipped below anyway.

    So two floors with the SAME set of boardable origin departures run a
    bit-identical search. That set is pinned by the earliest origin departure at
    or after the floor, which makes it the dedup key. A quiet station whose only
    departures are 07:15 / 13:40 / 18:05 runs 3 searches, not 16; floors past the
    last departure board nothing at all and are dropped outright.
    """
    best: dict[tuple[str, int], Journey] = {}
    if not trips:
        return {}
    display_offsets = display_offsets or {}
    origin_off = display_offsets.get(origin, 0)
    trip_stops, by_station = _index(trips)
    origin_deps = sorted(
        {
            dep
            for ti in by_station.get(origin, ())
            for station, _, dep in trip_stops[ti]
            if station == origin
        }
    )

    floors: dict[int, int] = {}  # earliest reachable origin departure -> a floor
    for dep_floor in range(5 * 60 - origin_off, 21 * 60 - origin_off, 60):
        i = bisect_left(origin_deps, dep_floor)
        if i == len(origin_deps):
            continue  # nothing left to board today; this floor reaches nothing
        floors.setdefault(origin_deps[i], dep_floor)

    for dep_floor in floors.values():
        arr, parent = _raptor(
            trips, origin, dep_floor, max_trains, transfer_min, footpaths or []
        )
        for k in range(1, max_trains + 1):
            for dest, t in arr[k].items():
                if dest == origin:
                    continue
                rec = _walk(parent, k, dest, origin)
                if rec is None:
                    continue
                trains, first_dep = rec
                duration = t - first_dep
                key = (dest, trains)
                current = best.get(key)
                # Only materialize Leg/Journey pydantic objects for a candidate
                # that is actually going to win its (dest, trains) tier -- most
                # aren't (see backlog AW): same strict-`<` tie-break, so the
                # winner is unchanged.
                if current is None or duration < current.duration_min:
                    legs = _build_legs(parent, k, dest, origin, display_offsets)
                    best[key] = Journey(trains=trains, duration_min=duration, legs=legs)

    out: dict[str, list[Journey]] = {}
    dests = {d for d, _ in best}
    for dest in dests:
        tiers: list[Journey] = []
        for k in range(1, max_trains + 1):
            j = best.get((dest, k))
            if j and (not tiers or j.duration_min < tiers[-1].duration_min):
                tiers.append(j)
        out[dest] = tiers
    return out
