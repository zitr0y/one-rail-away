import json

from pipeline.railpaths import collect_hops, parse_maxspeed


def _write_reach(tmp_path, origin, destinations):
    (tmp_path / f"reach_{origin}.json").write_text(json.dumps({
        "origin": origin, "computed_at": "x", "sample_date": "x",
        "destinations": destinations,
    }), encoding="utf-8")


def test_collect_hops_nonstop_and_via_legs(tmp_path):
    _write_reach(tmp_path, "s:a", [
        {"id": "s:d", "direct_per_day": 1, "journeys": [
            {"trains": 1, "duration_min": 60, "legs": [
                {"train": "T1", "dep": "", "arr": "", "from": "s:a", "to": "s:d",
                 "via": ["s:b", "s:c"]},
            ]},
            {"trains": 1, "duration_min": 90, "legs": [
                {"train": "T2", "dep": "", "arr": "", "from": "s:a", "to": "s:d", "via": []},
            ]},
        ]},
    ])
    assert collect_hops(tmp_path) == {
        ("s:a", "s:b"), ("s:b", "s:c"), ("s:c", "s:d"), ("s:a", "s:d"),
    }


def test_collect_hops_normalizes_direction_and_dedupes(tmp_path):
    leg_ab = {"train": "T", "dep": "", "arr": "", "from": "s:a", "to": "s:b", "via": []}
    leg_ba = {"train": "T", "dep": "", "arr": "", "from": "s:b", "to": "s:a", "via": []}
    _write_reach(tmp_path, "s:a", [{"id": "s:b", "direct_per_day": 1, "journeys": [
        {"trains": 1, "duration_min": 10, "legs": [leg_ab]}]}])
    _write_reach(tmp_path, "s:b", [{"id": "s:a", "direct_per_day": 1, "journeys": [
        {"trains": 1, "duration_min": 10, "legs": [leg_ba]}]}])
    assert collect_hops(tmp_path) == {("s:a", "s:b")}


def test_collect_hops_skips_self_pairs(tmp_path):
    _write_reach(tmp_path, "s:a", [{"id": "s:b", "direct_per_day": 1, "journeys": [
        {"trains": 1, "duration_min": 10, "legs": [
            {"train": "T", "dep": "", "arr": "", "from": "s:a", "to": "s:b", "via": ["s:a"]},
        ]}]}])
    assert collect_hops(tmp_path) == {("s:a", "s:b")}


def test_parse_maxspeed():
    assert parse_maxspeed(None) == 100.0
    assert parse_maxspeed("signals") == 100.0
    assert parse_maxspeed("160") == 160.0
    assert parse_maxspeed("120 mph") == 120 * 1.609344
    assert parse_maxspeed("5") == 10.0     # clamped up
    assert parse_maxspeed("400") == 320.0  # clamped down
