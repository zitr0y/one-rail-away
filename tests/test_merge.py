"""Tests for pipeline.merge: cross-feed station merging.

Precedence under test: alias override -> UIC regex on stop_id -> proximity
fallback (existing station <500 m AND same normalized name) -> fresh id.
"""

import pytest

from pipeline.config import FeedConfig
from pipeline.gtfs import RawStop
from pipeline.merge import PROXIMITY_M, _dist_m, _norm, merge_stations


def _cfg(**kw) -> FeedConfig:
    return FeedConfig(
        url="u", country=kw.pop("country", "XX"), license="t", route_allow=[], **kw
    )


# --- Brief tests -------------------------------------------------------------


def test_border_station_merges_via_uic():
    per_feed = {
        "landia": (
            [RawStop("st:3333333", "Gamma Hbf", 50.0, 10.0)],
            _cfg(uic_regex=r"(\d{7})", country="LA"),
        ),
        "borderia": (
            [RawStop("bs-3333333", "Gamma Central", 50.0001, 10.0001)],
            _cfg(uic_regex=r"(\d{7})", country="BO"),
        ),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1
    assert stations[0].id == "3333333" and stations[0].name == "Gamma Hbf"
    assert (
        mapping[("landia", "st:3333333")]
        == mapping[("borderia", "bs-3333333")]
        == "3333333"
    )


def test_proximity_fallback_merges_unmatched_ids():
    per_feed = {
        "a": ([RawStop("weird-id", "Same Place", 51.0, 7.0)], _cfg(uic_regex=r"^(\d{7})$")),
        "b": ([RawStop("other-id", "Same Place", 51.001, 7.001)], _cfg(uic_regex=r"^(\d{7})$")),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1
    assert mapping[("a", "weird-id")] == mapping[("b", "other-id")]


def test_alias_override_wins():
    per_feed = {"a": ([RawStop("odd", "X", 40.0, 4.0)], _cfg())}
    stations, mapping = merge_stations(per_feed, {"a:odd": "1234567"})
    assert mapping[("a", "odd")] == "1234567"


# --- #1 precedence: alias must beat a MATCHING UIC regex ---------------------


def test_alias_beats_matching_uic_regex():
    # stop_id "st:7654321" WOULD yield UIC 7654321 via the regex, but the alias
    # must win outright -> canonical is the alias target, not the UIC.
    per_feed = {"a": ([RawStop("st:7654321", "X", 40.0, 4.0)], _cfg(uic_regex=r"(\d{7})"))}
    _, mapping = merge_stations(per_feed, {"a:st:7654321": "9999999"})
    assert mapping[("a", "st:7654321")] == "9999999"


# --- #2 proximity requires BOTH name match AND <500 m ------------------------


def test_same_name_far_apart_does_not_merge():
    # Two "Hauptbahnhof" in different cities (~78 km apart) must stay distinct.
    per_feed = {
        "a": ([RawStop("id-a", "Hauptbahnhof", 50.0, 8.0)], _cfg(uic_regex=r"^(\d{7})$")),
        "b": ([RawStop("id-b", "Hauptbahnhof", 50.0, 9.0)], _cfg(uic_regex=r"^(\d{7})$")),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 2
    assert mapping[("a", "id-a")] != mapping[("b", "id-b")]


def test_different_name_close_together_does_not_merge():
    # Paris Est / Paris Nord are ~280 m apart but are genuinely different stations.
    per_feed = {
        "a": ([RawStop("id-a", "Paris Est", 48.8766, 2.3592)], _cfg(uic_regex=r"^(\d{7})$")),
        "b": ([RawStop("id-b", "Paris Nord", 48.8790, 2.3580)], _cfg(uic_regex=r"^(\d{7})$")),
    }
    stations, mapping = merge_stations(per_feed, {})
    # sanity: confirm they really are within the proximity radius
    assert _dist_m(48.8766, 2.3592, 48.8790, 2.3580) < PROXIMITY_M
    assert len(stations) == 2
    assert mapping[("a", "id-a")] != mapping[("b", "id-b")]


def test_proximity_uses_normalized_name():
    # "St. Gallen" vs "st gallen" normalize equal; within 500 m -> merge.
    per_feed = {
        "a": ([RawStop("id-a", "St. Gallen", 47.4223, 9.3702)], _cfg(uic_regex=r"^(\d{7})$")),
        "b": ([RawStop("id-b", "st gallen", 47.4224, 9.3703)], _cfg(uic_regex=r"^(\d{7})$")),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1
    assert mapping[("a", "id-a")] == mapping[("b", "id-b")]


# --- #3 _dist_m sanity check -------------------------------------------------


def test_dist_m_latitude_degree():
    # 1 degree of latitude is ~111.19 km regardless of longitude.
    d = _dist_m(50.0, 10.0, 51.0, 10.0)
    assert d == pytest.approx(111_190, rel=0.02)


def test_dist_m_longitude_degree_at_lat50():
    # At lat 50, 1 degree of longitude is ~71.47 km.
    d = _dist_m(50.0, 10.0, 50.0, 11.0)
    assert d == pytest.approx(71_470, rel=0.03)


# --- #4 UIC extraction from both id shapes, and no-digit fallthrough ---------


def test_uic_extracts_from_both_id_shapes():
    per_feed = {
        "landia": ([RawStop("st:3333333", "Gamma", 50.0, 10.0)], _cfg(uic_regex=r"(\d{7})")),
        "borderia": ([RawStop("bs-3333333", "Gamma", 50.5, 10.5)], _cfg(uic_regex=r"(\d{7})")),
    }
    _, mapping = merge_stations(per_feed, {})
    assert mapping[("landia", "st:3333333")] == "3333333"
    assert mapping[("borderia", "bs-3333333")] == "3333333"


def test_no_seven_digit_run_falls_through_to_fresh():
    # id has no 7-digit run: must not crash, must get a fresh id.
    per_feed = {"a": ([RawStop("platform-12", "Nowhere", 12.0, 34.0)], _cfg(uic_regex=r"(\d{7})"))}
    _, mapping = merge_stations(per_feed, {})
    assert mapping[("a", "platform-12")] == "x:a:platform-12"


# --- #6 8+ digit run must NOT yield a bogus 7-digit UIC ----------------------


def test_eight_digit_run_does_not_match_uic():
    # Real DE IFOPT id: the 8-digit run 12345678 must NOT be truncated to 1234567.
    per_feed = {
        "de": (
            [RawStop("de:08212:90:1:12345678", "Karlsruhe", 49.0, 8.4)],
            _cfg(uic_regex=r"(\d{7})"),
        )
    }
    _, mapping = merge_stations(per_feed, {})
    assert mapping[("de", "de:08212:90:1:12345678")] == "x:de:de:08212:90:1:12345678"


def test_seven_digit_run_still_matches_alongside_longer_runs():
    # An exact 7-digit run embedded among non-digit-bounded groups still resolves.
    per_feed = {"de": ([RawStop("de:99:0:7654321", "Foo", 49.0, 8.4)], _cfg(uic_regex=r"(\d{7})"))}
    _, mapping = merge_stations(per_feed, {})
    assert mapping[("de", "de:99:0:7654321")] == "7654321"


# --- #5 determinism: feed order does not change who registers first ----------


def test_feed_order_controls_precedence_and_is_deterministic():
    # Two feeds, same UIC, different names/coords. Feed ORDER is the documented
    # priority signal: the first feed in iteration order wins the display name.
    # The merger does NOT sort feed names -- it honors the caller's order -- and is
    # deterministic (same input order -> same result every time).
    landia = (
        [RawStop("st:3333333", "Gamma Hbf", 50.0, 10.0)],
        _cfg(uic_regex=r"(\d{7})", country="LA"),
    )
    borderia = (
        [RawStop("bs-3333333", "Gamma Central", 50.0001, 10.0001)],
        _cfg(uic_regex=r"(\d{7})", country="BO"),
    )

    landia_first, _ = merge_stations({"landia": landia, "borderia": borderia}, {})
    borderia_first, _ = merge_stations({"borderia": borderia, "landia": landia}, {})

    assert len(landia_first) == len(borderia_first) == 1
    # First feed in iteration order wins, so order flips the display name.
    assert landia_first[0].name == "Gamma Hbf" and landia_first[0].country == "LA"
    assert borderia_first[0].name == "Gamma Central" and borderia_first[0].country == "BO"

    # Determinism: repeating the same input order yields an identical result.
    again, _ = merge_stations({"landia": landia, "borderia": borderia}, {})
    assert again[0].name == landia_first[0].name and again[0].country == landia_first[0].country


# --- misc: country + coords come from the first (winning) feed ---------------


def test_winning_feed_sets_country_and_coords():
    landia = (
        [RawStop("st:3333333", "Gamma Hbf", 50.0, 10.0)],
        _cfg(uic_regex=r"(\d{7})", country="LA"),
    )
    borderia = (
        [RawStop("bs-3333333", "Gamma Central", 50.0001, 10.0001)],
        _cfg(uic_regex=r"(\d{7})", country="BO"),
    )
    stations, _ = merge_stations({"borderia": borderia, "landia": landia}, {})
    (gamma,) = stations
    # borderia is passed first, so its coords and country win.
    assert gamma.country == "BO"
    assert gamma.lat == 50.0001 and gamma.lon == 10.0001


def test_norm_strips_punctuation_and_case():
    assert _norm("St. Gallen") == _norm("st gallen") == "stgallen"


# --- accent transliteration: umlaut vs ASCII spelling must still proximity-merge ---


def test_umlaut_and_ascii_spelling_merge_via_proximity():
    # "München Hbf" (with umlaut) and "Munchen Hbf" (ASCII, accent dropped) refer to
    # the same physical station. No usable UIC in either id, no alias configured --
    # only _norm's transliteration (not mere deletion) can bridge them via proximity.
    per_feed = {
        "de": (
            [RawStop("de:platform-1", "München Hbf", 48.1402, 11.5581)],
            _cfg(uic_regex=r"^(\d{7})$"),
        ),
        "alt": (
            [RawStop("alt:platform-1", "Munchen Hbf", 48.1403, 11.5582)],
            _cfg(uic_regex=r"^(\d{7})$"),
        ),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1
    assert mapping[("de", "de:platform-1")] == mapping[("alt", "alt:platform-1")]


# --- coordinate-less stub resolution -----------------------------------------
#
# A stub (lat/lon None) is the foreign half of a cross-border trip: the feed
# carries the stop but no coordinate. It must NEVER create a canonical station.
# After the normal alias/UIC/proximity merge settles, each remaining stub is
# resolved by an UNAMBIGUOUS normalized-name match onto a real (coordinate-bearing)
# canonical station. Unmatched or ambiguous stubs are dropped (absent from the
# mapping) so the build stage strips them from trips.


def _real(feed, sid, name, lat, lon):
    return (feed, ([RawStop(sid, name, lat, lon)], _cfg(uic_regex=r"^(\d{7})$")))


def test_stub_resolves_to_real_station_by_name():
    per_feed = dict(
        [
            _real("de", "de:1", "Berlin Hbf", 52.525, 13.369),
            ("nl", ([RawStop("nl:stub", "Berlin Hbf", None, None)], _cfg(uic_regex=r"^(\d{7})$"))),
        ]
    )
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1  # stub created no new station
    assert mapping[("nl", "nl:stub")] == mapping[("de", "de:1")]


def test_stub_never_creates_a_canonical_station():
    # A stub with no real station to resolve onto is dropped, not registered.
    per_feed = {
        "nl": ([RawStop("nl:stub", "Ghost Halt", None, None)], _cfg(uic_regex=r"^(\d{7})$")),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert stations == []
    assert ("nl", "nl:stub") not in mapping


def test_ambiguous_stub_is_dropped():
    # Two distinct real stations share the stub's normalized name -> ambiguous,
    # so the stub is dropped rather than guessed onto either one.
    per_feed = dict(
        [
            _real("de", "de:1", "Nord", 52.0, 13.0),
            _real("fr", "fr:1", "Nord", 48.0, 2.0),
            ("nl", ([RawStop("nl:stub", "Nord", None, None)], _cfg(uic_regex=r"^(\d{7})$"))),
        ]
    )
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 2  # the two real stations; stub added none
    assert ("nl", "nl:stub") not in mapping


def test_stub_resolution_ignores_other_stubs():
    # A stub must resolve only onto a REAL station, never onto another stub, even
    # if their names match (two coordinate-less halves are not a resolution target).
    per_feed = {
        "nl": ([RawStop("nl:stub", "Wien Hbf", None, None)], _cfg(uic_regex=r"^(\d{7})$")),
        "fr": ([RawStop("fr:stub", "Wien Hbf", None, None)], _cfg(uic_regex=r"^(\d{7})$")),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert stations == []
    assert ("nl", "nl:stub") not in mapping and ("fr", "fr:stub") not in mapping


def test_alias_still_resolves_a_stub():
    # An explicit alias for a stub wins outright -- it maps onto the chosen
    # canonical station even though the stub has no coordinates.
    per_feed = dict(
        [
            _real("de", "de:1", "Real Station", 52.0, 13.0),
            ("nl", ([RawStop("nl:stub", "Whatever", None, None)], _cfg(uic_regex=r"^(\d{7})$"))),
        ]
    )
    # The de:1 UIC-less id falls to a fresh id; alias the stub straight onto it.
    canonical = merge_stations(per_feed, {})[1][("de", "de:1")]
    _, mapping = merge_stations(per_feed, {"nl:nl:stub": canonical})
    assert mapping[("nl", "nl:stub")] == canonical
