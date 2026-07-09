"""Known international trajectories as regression guards.

User-reported gaps (2026-07-09 feedback): border-split through-trains must stay
joined (pipeline/through.py) and foreign stations must carry their geographic
country (pipeline/geo.py). These tests validate the real pipeline OUTPUT and are
skipped on fresh clones without it; the unit suites validate the logic.

Deliberately NOT asserted: Berlin<->Warszawa. The EC 95 German half (Rzepin ->
Berlin Gesundbrunnen) runs 0x on sample date 2026-07-14 (construction); the
connection is genuinely absent from this data snapshot.
"""

import json
from pathlib import Path

import pytest

from server.app import EXONYMS, normalize

GRAPH = Path("data/graph")
OUT = Path("data/out")

pytestmark = pytest.mark.skipif(
    not (GRAPH / "trips.json").exists(), reason="real pipeline output not present"
)

# Canonical ids from the 2026-07 build (db_fern ids are stable internal ids; the
# alias table depends on the same stability, see feeds.toml).
WIEN = "x:db_fern:54514"
BUDAPEST_KELETI = "x:oebb:Phu:14216:27001535"
VENEZIA_SL = "x:oebb:it:22099:110:51:1"
VILLACH = "x:db_fern:527208"
BERLIN = "x:db_fern:569849"
PRAHA = "x:db_fern:549400"
WARSZAWA = "x:db_fern:419347"


def _trips():
    return json.loads((GRAPH / "trips.json").read_text(encoding="utf-8"))["trips"]


def _stations():
    return json.loads((GRAPH / "stations.json").read_text(encoding="utf-8"))["stations"]


def _serves(trip, station_id):
    return any(s["station"] == station_id for s in trip["stops"])


@pytest.mark.parametrize(
    ("a", "b"),
    [(WIEN, BUDAPEST_KELETI), (VILLACH, VENEZIA_SL), (BERLIN, PRAHA)],
    ids=["wien-budapest", "villach-venezia", "berlin-praha"],
)
def test_direct_international_trip_exists(a, b):
    assert any(_serves(t, a) and _serves(t, b) for t in _trips())


def test_foreign_station_countries_are_geographic():
    by_id = {s["id"]: s for s in _stations()}
    assert by_id[PRAHA]["country"] == "CZ"
    assert by_id[VENEZIA_SL]["country"] == "IT"
    assert by_id[BUDAPEST_KELETI]["country"] == "HU"
    assert by_id[WARSZAWA]["country"] == "PL"
    assert by_id[WIEN]["country"] == "AT"
    assert by_id[BERLIN]["country"] == "DE"


def test_exonym_targets_exist():
    names = [normalize(s["name"]) for s in _stations()]
    for native in sorted(set(EXONYMS.values())):
        assert any(native in n for n in names), f"exonym target {native!r} matches no station"


@pytest.mark.skipif(not (OUT / f"reach_{BERLIN}.json").exists(), reason="no Berlin reach file")
def test_berlin_praha_direct_reach():
    reach = json.loads((OUT / f"reach_{BERLIN}.json").read_text(encoding="utf-8"))
    dest = next(d for d in reach["destinations"] if d["id"] == PRAHA)
    # journeys are ascending in train count; EC Berlin->Praha is direct, ~4h15
    assert dest["journeys"][0]["trains"] == 1
    assert dest["journeys"][0]["duration_min"] < 300


@pytest.mark.skipif(not (OUT / f"reach_{WIEN}.json").exists(), reason="no Wien reach file")
def test_wien_budapest_direct_reach():
    reach = json.loads((OUT / f"reach_{WIEN}.json").read_text(encoding="utf-8"))
    dest = next(d for d in reach["destinations"] if d["id"] == BUDAPEST_KELETI)
    # direct railjet Wien->Budapest is ~2h40; pre-fix this showed 2 trains / 219 min
    assert dest["journeys"][0]["trains"] == 1
    assert dest["journeys"][0]["duration_min"] < 200
