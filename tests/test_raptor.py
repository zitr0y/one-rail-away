from datetime import date

from pipeline.gtfs import load_feed
from pipeline.merge import merge_stations
from pipeline.models import StopTime, Trip
from pipeline.raptor import compute_reachability, fmt
from tests.fixtures import make_fixture_feeds

SAMPLE = date(2026, 7, 14)
ALPHA, BETA, GAMMA, DELTA = "1111111", "2222222", "3333333", "4444444"


def _world(tmp_path):
    cfgs = make_fixture_feeds(tmp_path)
    per_feed, all_trips = {}, []
    for name in cfgs:
        stops, trips = load_feed(tmp_path / f"{name}.zip", cfgs[name], SAMPLE)
        per_feed[name] = (stops, cfgs[name])
        all_trips.append((name, trips))
    _, mapping = merge_stations(per_feed, {})
    trips = []
    for name, ts in all_trips:
        for t in ts:
            for s in t.stops:
                s.station = mapping[(name, s.station)]
            trips.append(t)
    return trips


# --- Brief's fixture-truth tests (do not weaken) ---------------------------


def test_nonstop_picks_fastest_direct_train(tmp_path):
    reach = compute_reachability(_world(tmp_path), ALPHA)
    beta = reach[BETA]
    assert beta[0].trains == 1 and beta[0].duration_min == 50  # IC 101, not IC 100
    assert beta[0].legs[0].train == "IC 101"


def test_one_stop_respects_min_transfer(tmp_path):
    reach = compute_reachability(_world(tmp_path), ALPHA)
    gamma = reach[GAMMA]
    # Direct IC 100 exists (120 min). IC 100->IC 300 (5-min transfer) is illegal,
    # so no 2-train journey can beat the direct one -> exactly one tier.
    assert [j.trains for j in gamma] == [1]
    assert gamma[0].duration_min == 120


def test_two_trains_cross_border(tmp_path):
    reach = compute_reachability(_world(tmp_path), ALPHA)
    delta = reach[DELTA]
    assert [j.trains for j in delta] == [2]
    assert delta[0].duration_min == 240  # 08:00 -> 12:00
    assert [leg.train for leg in delta[0].legs] == ["IC 100", "TGV 10"]
    assert delta[0].legs[0].via == [BETA]  # via-station for the polyline


def test_unreachable_station_absent(tmp_path):
    reach = compute_reachability(_world(tmp_path), DELTA)
    assert ALPHA not in reach  # no trains run backwards in the fixture


def test_fmt():
    assert fmt(8 * 60) == "08:00" and fmt(25 * 60 + 5) == "01:05"


# --- Added tests for danger zones the brief's Alpha-centric tests miss -----


def test_mid_route_boarding_beta_to_gamma(tmp_path):
    # Danger zone #3: best Beta->Gamma is IC 100 boarded MID-ROUTE at Beta
    # (09:02 -> 10:00 = 58 min), NOT IC 300 (09:05 -> 10:05 = 60 min).
    reach = compute_reachability(_world(tmp_path), BETA)
    gamma = reach[GAMMA]
    assert gamma[0].trains == 1
    assert gamma[0].duration_min == 58
    assert gamma[0].legs[0].train == "IC 100"
    assert gamma[0].legs[0].from_ == BETA
    assert gamma[0].legs[0].to == GAMMA
    assert gamma[0].legs[0].via == []


def test_alpha_to_delta_leg_boundaries(tmp_path):
    # Danger zone #4: leg-boundary / via correctness for the multi-leg journey.
    reach = compute_reachability(_world(tmp_path), ALPHA)
    delta = reach[DELTA]
    legs = delta[0].legs
    assert len(legs) == 2
    assert legs[0].from_ == ALPHA and legs[0].to == GAMMA and legs[0].via == [BETA]
    assert legs[1].from_ == GAMMA and legs[1].to == DELTA and legs[1].via == []
    # Chaining: first leg departs origin, each leg's `to` is next leg's boarding.
    assert legs[0].to == legs[1].from_
    assert legs[0].dep == "08:00" and legs[1].arr == "12:00"


def test_alpha_beta_uses_later_departure(tmp_path):
    # Danger zone #5: best Alpha->Beta (50 min) comes from IC 101 at 12:00,
    # a LATER departure than IC 100 at 08:00 (60 min). Duration must use the
    # journey's actual first departure, not the hourly floor.
    reach = compute_reachability(_world(tmp_path), ALPHA)
    beta = reach[BETA]
    assert beta[0].duration_min == 50
    assert beta[0].legs[0].dep == "12:00" and beta[0].legs[0].arr == "12:50"


# --- Synthetic-Trip unit tests (construct Trip objects directly) -----------


def _stop(station, arr, dep):
    return StopTime(station=station, arr=arr, dep=dep)


def test_transfer_boundary_exactly_10_is_legal():
    # Danger zone #2: ready = reached + transfer_min <= dep. Exactly 10 is LEGAL.
    # Times sit inside the 05:00-20:00 floor window so a floor can reach them.
    # Leg 1: O 600 -> A arr 700.  Leg 2 departs A at 710 (= 700 + 10) -> B 800.
    t1 = Trip(trip_id="t1", train="T1", stops=[_stop("O", 600, 600), _stop("A", 700, 700)])
    t2 = Trip(trip_id="t2", train="T2", stops=[_stop("A", 710, 710), _stop("B", 800, 800)])
    reach = compute_reachability([t1, t2], "O", transfer_min=10)
    assert "B" in reach
    b = reach["B"]
    assert b[-1].trains == 2
    assert [leg.train for leg in b[-1].legs] == ["T1", "T2"]


def test_transfer_boundary_9_is_illegal():
    # Same as above but leg 2 departs A at 709 (= 700 + 9 < 700 + 10) -> illegal.
    t1 = Trip(trip_id="t1", train="T1", stops=[_stop("O", 600, 600), _stop("A", 700, 700)])
    t2 = Trip(trip_id="t2", train="T2", stops=[_stop("A", 709, 709), _stop("B", 800, 800)])
    reach = compute_reachability([t1, t2], "O", transfer_min=10)
    assert "B" not in reach  # A is reachable but B is not (transfer too tight)
    assert "A" in reach


def test_origin_board_has_no_transfer_buffer():
    # Danger zone #2: buffer is 0 at origin. A trip departing origin only 1 min
    # after the floor-implied readiness must still be boardable at the origin.
    t = Trip(trip_id="t", train="T", stops=[_stop("O", 301, 301), _stop("X", 400, 400)])
    reach = compute_reachability([t], "O", transfer_min=10)
    # Floor 05:00=300 <= dep 301; buffer 0 at origin -> boardable, X reachable.
    assert "X" in reach
    assert reach["X"][0].legs[0].dep == "05:01"


def test_parent_carryover_tier_is_true_leg_count():
    # Danger zone #1 + #6: a station reachable in 1 train must not be reported as
    # a 2-train journey. Reconstruction must yield the TRUE leg count and the
    # tier-collapse must file it under tier 1 only.
    t = Trip(trip_id="t", train="T", stops=[_stop("O", 500, 500), _stop("X", 560, 560)])
    reach = compute_reachability([t], "O", max_trains=3)
    assert [j.trains for j in reach["X"]] == [1]  # not [1, 1, 1] or any 2/3 tier
    assert reach["X"][0].duration_min == 60


def test_post_midnight_arithmetic_does_not_wrap():
    # Danger zone #7: dep 23:50 (1430) -> arr 01:10 next day (1510), 80 min.
    # Reachable from floor 20:00 (1200 <= 1430). Duration must NOT wrap.
    t = Trip(trip_id="t", train="Night", stops=[_stop("O", 1430, 1430), _stop("X", 1510, 1510)])
    reach = compute_reachability([t], "O")
    assert "X" in reach
    j = reach["X"][0]
    assert j.duration_min == 80
    assert j.legs[0].dep == "23:50" and j.legs[0].arr == "01:10"  # fmt wraps display


def test_genuine_tie_drops_slower_train_count_tier():
    # Danger zone #8: the tier collapse only keeps a higher train-count tier if it
    # is STRICTLY faster (`j.duration_min < tiers[-1].duration_min`). A genuine tie
    # between a 1-train and a legal 2-train journey to the same destination must
    # collapse to exactly one tier (the 1-train one), not two.
    #
    # Arithmetic (minutes since midnight; floors are hourly 05:00-20:00 = 300..1200):
    #   T1 (1 train, direct):  O --dep 1080 (18:00)--> D --arr 1200 (20:00)
    #       duration = 1200 - 1080 = 120
    #   T2a (leg 1 of 2-train): O --dep 600 (10:00)--> A --arr 650 (10:50)
    #   T2b (leg 2 of 2-train): A --dep 660 (11:00)--> D --arr 720 (12:00)
    #       transfer at A = 660 - 650 = 10 >= transfer_min(10) -> LEGAL
    #       duration = 720 - 600 = 120  <- exactly equal to the 1-train duration
    #   Both trip departures (1080 and 600) sit exactly on hourly floor values, so
    #   both journeys are found (each from its own floor) with duration 120. Since
    #   120 is not < 120, compute_reachability's collapse must drop the 2-train
    #   tier and report only the 1-train tier.
    t1 = Trip(trip_id="t1", train="Direct", stops=[_stop("O", 1080, 1080), _stop("D", 1200, 1200)])
    t2a = Trip(trip_id="t2a", train="Feeder", stops=[_stop("O", 600, 600), _stop("A", 650, 650)])
    t2b = Trip(trip_id="t2b", train="Onward", stops=[_stop("A", 660, 660), _stop("D", 720, 720)])
    reach = compute_reachability([t1, t2a, t2b], "O", max_trains=2, transfer_min=10)
    dest = reach["D"]
    assert [j.trains for j in dest] == [1]
    assert dest[0].trains == 1
    assert dest[0].duration_min == 120
