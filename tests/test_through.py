from pipeline.models import StopTime, Trip
from pipeline.through import join_through_services


def _trip(tid, train, *stops):
    return Trip(
        trip_id=tid,
        train=train,
        stops=[StopTime(station=s, arr=a, dep=d) for s, a, d in stops],
    )


def test_joins_split_through_service():
    a = _trip("A", "RJX 19929", ("kufstein", 600, 600), ("hegyeshalom", 700, 702))
    b = _trip("B", "RJX 19929", ("hegyeshalom", 700, 715), ("budapest", 760, 760))
    out = join_through_services([a, b])
    assert len(out) == 1
    t = out[0]
    assert t.trip_id == "A+B"
    assert [s.station for s in t.stops] == ["kufstein", "hegyeshalom", "budapest"]
    # boundary stop keeps A's arrival and B's departure
    assert (t.stops[1].arr, t.stops[1].dep) == (700, 715)


def test_join_preserves_seasonal_evidence_from_either_segment():
    a = _trip("A", "RJX 19929", ("kufstein", 600, 600), ("hegyeshalom", 700, 702))
    b = _trip("B", "RJX 19929", ("hegyeshalom", 700, 715), ("budapest", 760, 760))
    b.seasonal = True

    [joined] = join_through_services([a, b])

    assert joined.seasonal is True


def test_does_not_mutate_inputs():
    a = _trip("A", "RJX 1", ("x", 0, 0), ("y", 60, 60))
    b = _trip("B", "RJX 1", ("y", 60, 70), ("z", 120, 120))
    join_through_services([a, b])
    assert len(a.stops) == 2 and len(b.stops) == 2


def test_unnumbered_label_not_joined():
    a = _trip("A", "EC", ("x", 0, 0), ("y", 60, 60))
    b = _trip("B", "EC", ("y", 60, 70), ("z", 120, 120))
    assert len(join_through_services([a, b])) == 2


def test_label_mismatch_not_joined():
    a = _trip("A", "RJX 1", ("x", 0, 0), ("y", 60, 60))
    b = _trip("B", "RJX 2", ("y", 60, 70), ("z", 120, 120))
    assert len(join_through_services([a, b])) == 2


def test_gap_out_of_range_not_joined():
    a = _trip("A", "RJX 1", ("x", 0, 0), ("y", 60, 60))
    early = _trip("B", "RJX 1", ("y", 55, 58), ("z", 120, 120))  # departs before A arrives
    late = _trip("C", "RJX 1", ("y", 120, 121), ("z", 180, 180))  # 61 min gap
    assert len(join_through_services([a, early])) == 2
    assert len(join_through_services([a, late])) == 2


def test_return_trip_not_joined():
    # Out+return share the label and the terminus; the revisit guard must reject.
    out_ = _trip("A", "ICE 82", ("frankfurt", 0, 0), ("paris", 240, 240))
    ret = _trip("B", "ICE 82", ("paris", 240, 270), ("frankfurt", 510, 510))
    assert len(join_through_services([out_, ret])) == 2


def test_equal_gap_ambiguity_skipped():
    a = _trip("A", "RJX 1", ("x", 0, 0), ("y", 60, 60))
    b1 = _trip("B1", "RJX 1", ("y", 60, 70), ("z", 120, 120))
    b2 = _trip("B2", "RJX 1", ("y", 60, 70), ("w", 130, 130))
    assert len(join_through_services([a, b1, b2])) == 3


def test_smaller_gap_wins_unambiguously():
    a = _trip("A", "RJX 1", ("x", 0, 0), ("y", 60, 60))
    near = _trip("B", "RJX 1", ("y", 60, 65), ("z", 120, 120))
    far = _trip("C", "RJX 1", ("y", 60, 90), ("w", 150, 150))
    out = join_through_services([a, near, far])
    joined = next(t for t in out if "+" in t.trip_id)
    assert joined.trip_id == "A+B"
    assert len(out) == 2  # A+B, plus C untouched


def test_three_segment_chain_joins_fully():
    a = _trip("A", "RJX 134", ("venezia", 0, 0), ("tarvisio", 100, 100))
    b = _trip("B", "RJX 134", ("tarvisio", 100, 110), ("villach", 150, 150))
    c = _trip("C", "RJX 134", ("villach", 150, 155), ("klagenfurt", 190, 190))
    out = join_through_services([a, b, c])
    assert len(out) == 1
    assert [s.station for s in out[0].stops] == [
        "venezia",
        "tarvisio",
        "villach",
        "klagenfurt",
    ]
