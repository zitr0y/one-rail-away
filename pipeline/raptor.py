"""RAPTOR-style reachability core.

Answers: which stations can you reach from an origin using <= max_trains trains,
and how fast. For each destination we report the best journey per train-count tier
(ascending `trains`, each strictly faster than the previous; non-improving tiers
omitted). Duration = arrival - actual first departure, minimized over hourly
departure floors 05:00-20:00.

All times are minutes since midnight of the sample date and MAY exceed 1440
(post-midnight arrivals). Arithmetic never wraps; only `fmt` wraps for display.
"""

from pipeline.models import Journey, Leg, Trip

INF = 10**9


def fmt(minutes: int) -> str:
    """Format minutes-since-midnight as 'HH:MM', wrapping the hour modulo 24."""
    return f"{minutes // 60 % 24:02d}:{minutes % 60:02d}"


def _raptor(trips, origin, dep_floor, max_trains, transfer_min):
    """Round k = earliest arrival using <= k trains, departing origin no earlier
    than dep_floor.

    parent[(k, station)] = (trip, board_station, board_dep, alight_arr,
    board_idx, alight_idx). Board/alight indices are indices into trip.stops and
    are used by `_reconstruct` to slice the via list.
    """
    arr: list[dict[str, int]] = [{origin: dep_floor}]
    parent: dict[tuple[int, str], tuple] = {}
    for k in range(1, max_trains + 1):
        cur = dict(arr[k - 1])
        # Carry parent pointers forward so a station reached with fewer trains
        # can still be reconstructed at a later round (true leg count < k).
        for st in arr[k - 1]:
            if (k - 1, st) in parent:
                parent[(k, st)] = parent[(k - 1, st)]
        for trip in trips:
            board = None  # (station, dep, idx)
            for i, s in enumerate(trip.stops):
                if board is not None and s.arr < cur.get(s.station, INF):
                    cur[s.station] = s.arr
                    parent[(k, s.station)] = (trip, board[0], board[1], s.arr, board[2], i)
                # Consider boarding here if we are not already aboard AND we were
                # here (via <= k-1 trains) early enough to make the departure.
                # Buffer is 0 at the origin (no transfer), transfer_min elsewhere.
                # Mid-route boarding is allowed: this runs at every stop, not just
                # the first.
                reached = arr[k - 1].get(s.station, INF)
                buffer = 0 if s.station == origin else transfer_min
                if board is None and reached + buffer <= s.dep:
                    board = (s.station, s.dep, i)
        arr.append(cur)
    return arr, parent


def _reconstruct(parent, k, dest, origin):
    """Walk parent pointers back to the origin.

    Returns (legs, first_dep_minutes) or None. Legs are ordered origin-first;
    each leg's `to` equals the next leg's boarding station; via lists exclude the
    two endpoints.
    """
    legs: list[Leg] = []
    st, kk = dest, k
    while st != origin:
        p = parent.get((kk, st))
        if p is None:
            return None
        trip, b_st, b_dep, a_arr, bi, ai = p
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
        if kk < 0:
            return None
    legs.reverse()
    # The last pointer we walked (deepest in the loop) is the first leg; its
    # board_dep is the true origin departure. Recover it unwrapped from the
    # parent chain rather than re-parsing the wrapped "HH:MM" string, so
    # duration stays exact for post-midnight departures.
    first_dep = _origin_dep_minutes(parent, dest, k, origin)
    return legs, first_dep


def _origin_dep_minutes(parent, dest, k, origin):
    """Recover the origin departure minute (unwrapped) by walking to the origin."""
    st, kk = dest, k
    dep = None
    while st != origin:
        _, b_st, b_dep, _, _, _ = parent[(kk, st)]
        dep = b_dep
        st, kk = b_st, kk - 1
    return dep


def compute_reachability(
    trips: list[Trip], origin: str, max_trains: int = 3, transfer_min: int = 10
) -> dict[str, list[Journey]]:
    """Best journey per (destination, train-count) tier, minimized over hourly
    departure floors 05:00-20:00, then collapsed to strictly-improving tiers."""
    best: dict[tuple[str, int], Journey] = {}
    for dep_floor in range(5 * 60, 21 * 60, 60):
        arr, parent = _raptor(trips, origin, dep_floor, max_trains, transfer_min)
        for k in range(1, max_trains + 1):
            for dest, t in arr[k].items():
                if dest == origin:
                    continue
                rec = _reconstruct(parent, k, dest, origin)
                if rec is None:
                    continue
                legs, first_dep = rec
                journey = Journey(trains=len(legs), duration_min=t - first_dep, legs=legs)
                key = (dest, journey.trains)
                if key not in best or journey.duration_min < best[key].duration_min:
                    best[key] = journey

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
