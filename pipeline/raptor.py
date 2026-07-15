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

from pipeline.models import Journey, Leg, Trip

INF = 10**9


def fmt(minutes: int) -> str:
    """Format minutes-since-midnight as 'HH:MM', wrapping the hour modulo 24."""
    return f"{minutes // 60 % 24:02d}:{minutes % 60:02d}"


_INDEX_CACHE: dict[int, tuple[list, list, dict[str, list[int]]]] = {}


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


def _raptor(trips, origin, dep_floor, max_trains, transfer_min):
    """Round k = earliest arrival using <= k trains, departing origin no earlier
    than dep_floor.

    parent[(k, station)] = (trip, board_station, board_dep, alight_arr,
    board_idx, alight_idx). Board/alight indices are indices into trip.stops and
    are used by `_build_legs` to slice the via list.

    Only trips calling at a station reached in round k-1 are scanned. A trip
    touching no such station fails the boarding test at every stop, so it can
    never write: skipping it is exact, not an approximation. Candidates are
    walked in ascending trip index -- the order a full scan would have used --
    because `cur` is read back as it is written within a round, so scan order
    decides which trip wins an equal-arrival tie, and hence which route we show.
    """
    trip_stops, by_station = _index(trips)
    arr: list[dict[str, int]] = [{origin: dep_floor}]
    parent: dict[tuple[int, str], tuple] = {}
    n_trips = len(trips)
    for k in range(1, max_trains + 1):
        prev = arr[k - 1]
        cur = dict(prev)
        # Carry parent pointers forward so a station reached with fewer trains
        # can still be reconstructed at a later round (true leg count < k).
        for st in prev:
            if (k - 1, st) in parent:
                parent[(k, st)] = parent[(k - 1, st)]

        # Only trips calling somewhere we already stand can ever be boarded.
        candidates: set[int] = set()
        for st in prev:
            hits = by_station.get(st)
            if hits:
                candidates.update(hits)
        scan = range(n_trips) if len(candidates) == n_trips else sorted(candidates)

        prev_get, cur_get = prev.get, cur.get
        for ti in scan:
            board = None  # (station, dep, idx)
            for i, (station, s_arr, s_dep) in enumerate(trip_stops[ti]):
                if board is not None:
                    if s_arr < cur_get(station, INF):
                        cur[station] = s_arr
                        parent[(k, station)] = (
                            trips[ti], board[0], board[1], s_arr, board[2], i
                        )
                # Consider boarding here if we are not already aboard AND we were
                # here (via <= k-1 trains) early enough to make the departure.
                # Buffer is 0 at the origin (no transfer), transfer_min elsewhere.
                # Mid-route boarding is allowed: this runs at every stop, not just
                # the first.
                elif prev_get(station, INF) + (0 if station == origin else transfer_min) <= s_dep:
                    board = (station, s_dep, i)
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
        _, b_st, b_dep, _, _, _ = p
        first_dep = b_dep
        st, kk = b_st, kk - 1
        trains += 1
        if kk < 0:
            return None
    return trains, first_dep


def _build_legs(parent, k, dest, origin):
    """Walk parent pointers back to the origin, materializing `Leg` objects.

    Only called once a candidate is already known to win its (dest, trains)
    tier (see `compute_reachability`), so the earlier allocation-free `_walk`
    is not wasted work for the many candidates that don't. Legs are ordered
    origin-first; each leg's `to` equals the next leg's boarding station; via
    lists exclude the two endpoints. Assumes the chain is valid -- callers
    must have already confirmed this via `_walk`.
    """
    legs: list[Leg] = []
    st, kk = dest, k
    while st != origin:
        trip, b_st, b_dep, a_arr, bi, ai = parent[(kk, st)]
        legs.append(
            Leg(
                train=trip.train,
                dep=fmt(b_dep),
                arr=fmt(a_arr),
                **{"from": b_st},
                to=st,
                via=[x.station for x in trip.stops[bi + 1 : ai]],
                feeds=trip.feeds,
            )
        )
        # Step back to the station we boarded this leg at, one fewer train.
        st, kk = b_st, kk - 1
    legs.reverse()
    return legs


def compute_reachability(
    trips: list[Trip], origin: str, max_trains: int = 3, transfer_min: int = 10
) -> dict[str, list[Journey]]:
    """Best journey per (destination, train-count) tier, minimized over hourly
    departure floors 05:00-20:00, then collapsed to strictly-improving tiers.

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
    for dep_floor in range(5 * 60, 21 * 60, 60):
        i = bisect_left(origin_deps, dep_floor)
        if i == len(origin_deps):
            continue  # nothing left to board today; this floor reaches nothing
        floors.setdefault(origin_deps[i], dep_floor)

    for dep_floor in floors.values():
        arr, parent = _raptor(trips, origin, dep_floor, max_trains, transfer_min)
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
                    legs = _build_legs(parent, k, dest, origin)
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
