"""Tests for pipeline.merge: cross-feed station merging.

Precedence under test: alias override -> UIC regex on stop_id -> proximity
fallback (existing station <500 m AND same normalized name) -> fresh id.
"""

import tomllib
from pathlib import Path

import pytest

from pipeline.config import FeedConfig
from pipeline.gtfs import RawStop
from pipeline.merge import PROXIMITY_M, _dist_m, _norm, merge_stations


def _cfg(**kw) -> FeedConfig:
    return FeedConfig(url="u", country=kw.pop("country", "XX"), license="t", route_allow=[], **kw)


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
    assert mapping[("landia", "st:3333333")] == mapping[("borderia", "bs-3333333")] == "3333333"


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


def test_production_aliases_merge_current_duplicate_validation_pairs():
    """Keep feed-id churn from making the full production build abort."""
    aliases = tomllib.loads(Path("station_aliases.toml").read_text())["aliases"]
    per_feed = {
        "db_fern": (
            [
                RawStop("464324", "Dornbirn", 47.414, 9.742),
                RawStop("335019", "Feldkirch", 47.238, 9.603),
                RawStop("338323", "Erfurt Hbf", 50.972, 11.038),
            ],
            _cfg(country="DE", uic_regex=r"(\d{7})"),
        ),
        "sncf": (
            [RawStop("StopArea:OCE80160432", "Erfurt Hbf", 50.9721, 11.0381)],
            _cfg(country="FR"),
        ),
        "oebb": (
            [
                RawStop("8102329", "Dornbirn", 47.4141, 9.7421),
                RawStop("8101236", "Feldkirch", 47.2381, 9.6031),
            ],
            _cfg(country="AT", uic_regex=r"(\d{7})"),
        ),
    }

    stations, mapping = merge_stations(per_feed, aliases)

    assert len(stations) == 3
    assert mapping[("db_fern", "464324")] == mapping[("oebb", "8102329")] == "8102329"
    assert mapping[("db_fern", "335019")] == mapping[("oebb", "8101236")] == "8101236"
    assert (
        mapping[("sncf", "StopArea:OCE80160432")]
        == mapping[("db_fern", "338323")]
        == "x:db_fern:338323"
    )


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


def test_norm_equates_german_station_words():
    # Real cross-feed pairs (db_fern vs oebb/ns, all <50 m apart in the 2026-07
    # build): "Hauptbahnhof" is spelled out or abbreviated "Hbf", small stations
    # carry a trailing "Bahnhof", and db_fern parent stations prefix the
    # S-Bahn/U-Bahn marker "S+U ". All three must normalize equal so proximity
    # can merge them.
    assert _norm("München Hauptbahnhof") == _norm("München Hbf") == "munchenhbf"
    assert _norm("Rosenheim Bahnhof") == _norm("Rosenheim") == "rosenheim"
    assert _norm("S+U Berlin Hauptbahnhof") == _norm("Berlin Hauptbahnhof") == "berlinhbf"
    # "Bahnhof" is stripped only as a TRAILING word.
    assert _norm("Bahnhof, Elsterwerda") == "bahnhofelsterwerda"
    # "München Ostbahnhof" == "München Ost" (ns stub vs oebb name, same station).
    assert _norm("München Ostbahnhof") == _norm("München Ost") == "munchenost"


def test_norm_stroke_letters():
    # Poland's 'Główny' -> 'glowny' (instead of dropping 'ł' to 'gowny')
    assert _norm("Główny") == "glowny"
    assert _norm("GŁÓWNY") == "glowny"

    # ø and đ examples
    assert _norm("Rødekro") == "rodekro"
    assert _norm("RØDEKRO") == "rodekro"
    assert _norm("Đurđevac") == "durdevac"
    assert _norm("ĐURĐEVAC") == "durdevac"

    # œ and æ examples
    assert _norm("Gare de l'Est-œst") == "garedelestoest"
    assert _norm("Ærøskøbing") == "aeroskobing"

    # Existing ue/oe/ae behavior is unchanged (digraphs are NOT converted to umlauts,
    # and umlauts normalize to their single-character base under NFKD)
    assert _norm("München") == "munchen"
    assert _norm("Muenchen") == "muenchen"
    assert _norm("München") != _norm("Muenchen")


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


# --- #7 UIC fallback: an unknown UIC code proximity-merges before minting ----
#
# Before 2026-07-10 a UIC match was terminal: an unknown code was minted as
# canonical without ever running the proximity+name check, duplicating any same
# station already registered under a non-UIC id (every sncf StopArea:OCE... and
# db_fern internal id). Each collision needed a manual station_aliases.toml
# entry (Konstanz, Mulhouse, Frasne). Spec:
# docs/superpowers/specs/2026-07-10-uic-merge-gap-design.md


def test_uic_stop_merges_onto_existing_non_uic_station():
    # sncf-style feed (no uic_regex) registers first under a fresh x: id; a later
    # feed's UIC stop for the same station must proximity-merge instead of
    # minting a duplicate canonical.
    per_feed = {
        "sncfish": (
            [RawStop("StopArea:OCE87686006", "Gare Centrale", 50.0, 10.0)],
            _cfg(),
        ),
        "sbbish": (
            [RawStop("st:8768600", "Gare Centrale", 50.0001, 10.0001)],
            _cfg(uic_regex=r"(\d{7})"),
        ),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1
    assert stations[0].id == "x:sncfish:StopArea:OCE87686006"  # no id churn
    assert (
        mapping[("sncfish", "StopArea:OCE87686006")]
        == mapping[("sbbish", "st:8768600")]
        == "x:sncfish:StopArea:OCE87686006"
    )


def test_uic_stop_far_from_same_name_station_mints_uic_canonical():
    # Same name but ~1.1 km apart: fallback must NOT fire; the code is minted
    # exactly as before.
    per_feed = {
        "a": ([RawStop("weird", "Neustadt", 50.0, 10.0)], _cfg()),
        "b": ([RawStop("st:1234567", "Neustadt", 50.01, 10.0)], _cfg(uic_regex=r"(\d{7})")),
    }
    assert _dist_m(50.0, 10.0, 50.01, 10.0) > PROXIMITY_M  # sanity
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 2
    assert mapping[("b", "st:1234567")] == "1234567"


def test_uic_stop_near_different_name_station_mints_uic_canonical():
    # Paris Est / Paris Nord are ~280 m apart but genuinely different stations:
    # different normalized name -> no fallback merge.
    per_feed = {
        "a": ([RawStop("weird", "Paris Est", 48.8766, 2.3592)], _cfg()),
        "b": (
            [RawStop("st:1234567", "Paris Nord", 48.8790, 2.3580)],
            _cfg(uic_regex=r"(\d{7})"),
        ),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 2
    assert mapping[("b", "st:1234567")] == "1234567"


def test_same_uic_code_from_third_feed_follows_fallback_merge():
    # After 8768600 fallback-merges onto the x: station, a THIRD feed carrying
    # the same code must land there too -- even offset >500 m with a different
    # spelling, where proximity alone could never match (uic_aliases table).
    per_feed = {
        "sncfish": (
            [RawStop("StopArea:OCE87686006", "Gare Centrale", 50.0, 10.0)],
            _cfg(),
        ),
        "sbbish": (
            [RawStop("st:8768600", "Gare Centrale", 50.0001, 10.0001)],
            _cfg(uic_regex=r"(\d{7})"),
        ),
        "oebbish": (
            [RawStop("bs-8768600", "Zentralbahnhof", 50.02, 10.02)],
            _cfg(uic_regex=r"(\d{7})"),
        ),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1
    assert mapping[("oebbish", "bs-8768600")] == "x:sncfish:StopArea:OCE87686006"


def test_uic_stop_merges_onto_different_uic_canonical():
    # Dual-code border station (same building, FR 87... and CH 85... codes):
    # the second UIC identity <500 m away with the same normalized name merges
    # onto the first. Symmetric with rule-3 proximity merging (user decision
    # 2026-07-10).
    per_feed = {
        "fr": (
            [RawStop("st:8718206", "Mulhouse Ville", 47.7418, 7.3428)],
            _cfg(uic_regex=r"(\d{7})"),
        ),
        "ch": (
            [RawStop("st:8500090", "Mulhouse Ville", 47.7419, 7.3429)],
            _cfg(uic_regex=r"(\d{7})"),
        ),
    }
    stations, mapping = merge_stations(per_feed, {})
    assert len(stations) == 1
    assert mapping[("fr", "st:8718206")] == mapping[("ch", "st:8500090")] == "8718206"


def test_alias_beats_uic_fallback_merge():
    # The stop WOULD fallback-merge onto the nearby same-name station, but an
    # explicit alias must still win outright (precedence rule 1 unchanged).
    per_feed = {
        "a": ([RawStop("weird", "Gare Centrale", 50.0, 10.0)], _cfg()),
        "b": (
            [RawStop("st:8768600", "Gare Centrale", 50.0001, 10.0001)],
            _cfg(uic_regex=r"(\d{7})"),
        ),
    }
    _, mapping = merge_stations(per_feed, {"b:st:8768600": "9999999"})
    assert mapping[("b", "st:8768600")] == "9999999"
