import json

import pytest
from fastapi.testclient import TestClient

from server.app import create_app, normalize


def _client(tmp_path):
    stations = [
        {
            "id": "1",
            "name": "München Hbf",
            "lat": 48.1,
            "lon": 11.5,
            "country": "DE",
            "has_reach": True,
        },
        {
            "id": "2",
            "name": "München Ost",
            "lat": 48.1,
            "lon": 11.6,
            "country": "DE",
            "has_reach": True,
        },
        {
            "id": "3",
            "name": "Bad München-Dorf",
            "lat": 48.2,
            "lon": 11.7,
            "country": "DE",
            "has_reach": True,
        },
        {
            "id": "4",
            "name": "Münchenberg",
            "lat": 49.0,
            "lon": 12.0,
            "country": "DE",
            "has_reach": False,
        },
        {
            "id": "5",
            "name": "München",
            "lat": 48.1,
            "lon": 11.5,
            "country": "DE",
            "has_reach": True,
        },
    ]
    (tmp_path / "stations.json").write_text(json.dumps({"stations": stations}))
    for s in stations:
        if s["has_reach"]:
            (tmp_path / f"reach_{s['id']}.json").write_text(json.dumps({"origin": s["id"]}))
    return TestClient(create_app(tmp_path))


def test_normalize_strips_accents():
    assert normalize("München") == "munchen"
    assert normalize("Zürich HB") == "zurich hb"


def test_search_prefix_beats_substring_and_skips_no_reach(tmp_path):
    got = _client(tmp_path).get("/api/stations/search", params={"q": "munchen"}).json()["stations"]
    names = [s["name"] for s in got]
    assert names[0] == "München"  # prefix + shortest normalized name wins the tie-break
    assert "Bad München-Dorf" in names  # substring still found
    assert all(s["id"] != "4" for s in got)  # has_reach=False excluded


def test_search_tier_tie_break_prefers_shorter_name_even_when_inserted_later(tmp_path):
    # "München" is appended after two longer tier-0 (prefix) matches of equal length
    # ("München Hbf", "München Ost" both normalize to 11 chars). A stable sort on
    # insertion order alone would keep "München Hbf" first; only a real length
    # tie-break promotes "München" (7 chars) to the top.
    got = _client(tmp_path).get("/api/stations/search", params={"q": "munchen"}).json()["stations"]
    names = [s["name"] for s in got]
    assert names[0] == "München"


def test_search_only_returns_stations_with_reach_file_on_disk(tmp_path):
    # Simulates a fresh clone: stations.json flags more stations has_reach=True than
    # there are reach_*.json files on disk (e.g. a partial sample or a full pipeline
    # run's stations.json paired with only a handful of force-added sample reach
    # files). Search must derive has_reach from file presence, not trust the stale
    # flag, so every result is actually fetchable via /api/reach/{id}.
    stations = [
        {
            "id": "1",
            "name": "München Hbf",
            "lat": 48.1,
            "lon": 11.5,
            "country": "DE",
            "has_reach": True,
        },
        {
            "id": "2",
            "name": "München Ost",
            "lat": 48.1,
            "lon": 11.6,
            "country": "DE",
            "has_reach": True,
        },
        {
            "id": "5",
            "name": "München",
            "lat": 48.1,
            "lon": 11.5,
            "country": "DE",
            "has_reach": True,
        },
    ]
    (tmp_path / "stations.json").write_text(json.dumps({"stations": stations}))
    # Only station "1" has a reach file on disk; "2" and "5" are flagged
    # has_reach=True in stations.json but have no file (the fresh-clone case).
    (tmp_path / "reach_1.json").write_text(json.dumps({"origin": "1"}))
    client = TestClient(create_app(tmp_path))

    got = client.get("/api/stations/search", params={"q": "munchen"}).json()["stations"]
    ids = {s["id"] for s in got}

    assert ids == {"1"}
    for s in got:
        assert s["has_reach"] is True
        assert client.get(f"/api/reach/{s['id']}").status_code == 200


def _exonym_client(tmp_path):
    stations = [
        {
            "id": "p1",
            "name": "Praha hl.n.",
            "lat": 50.08,
            "lon": 14.44,
            "country": "CZ",
            "has_reach": True,
        },
        {
            "id": "k1",
            "name": "Köln Hbf",
            "lat": 50.94,
            "lon": 6.96,
            "country": "DE",
            "has_reach": True,
        },
        {
            "id": "b1",
            "name": "Barcelona-Sants",
            "lat": 41.38,
            "lon": 2.14,
            "country": "ES",
            "has_reach": True,
        },
        {
            "id": "w1",
            "name": "Wien Hbf",
            "lat": 48.19,
            "lon": 16.38,
            "country": "AT",
            "has_reach": True,
        },
        {
            "id": "r1",
            "name": "Roma Termini",
            "lat": 41.9,
            "lon": 12.5,
            "country": "IT",
            "has_reach": True,
        },
        {
            "id": "c1",
            "name": "København H",
            "lat": 55.7,
            "lon": 12.6,
            "country": "DK",
            "has_reach": True,
        },
        {
            "id": "h1",
            "name": "Den Haag Centraal",
            "lat": 52.1,
            "lon": 4.3,
            "country": "NL",
            "has_reach": True,
        },
        {
            "id": "bu1",
            "name": "București Nord",
            "lat": 44.4,
            "lon": 26.1,
            "country": "RO",
            "has_reach": True,
        },
        {
            "id": "l1",
            "name": "Łódź Fabryczna",
            "lat": 51.8,
            "lon": 19.5,
            "country": "PL",
            "has_reach": True,
        },
    ]
    (tmp_path / "stations.json").write_text(json.dumps({"stations": stations}))
    for s in stations:
        (tmp_path / f"reach_{s['id']}.json").write_text("{}")
    return TestClient(create_app(tmp_path))


def _ids(resp):
    return [s["id"] for s in resp.json()["stations"]]


def test_search_english_exonym(tmp_path):
    c = _exonym_client(tmp_path)
    assert _ids(c.get("/api/stations/search", params={"q": "prague"})) == ["p1"]
    # "barcelona" is now the native name; search finds it directly.
    assert _ids(c.get("/api/stations/search", params={"q": "barcelona"})) == ["b1"]


def test_search_french_exonym_barcelone(tmp_path):
    """After the EXONYMS flip, searching 'barcelone' (French spelling) still finds
    Barcelona-Sants via the exonym table."""
    c = _exonym_client(tmp_path)
    assert _ids(c.get("/api/stations/search", params={"q": "barcelone"})) == ["b1"]


def test_search_german_exonym_and_transliteration(tmp_path):
    c = _exonym_client(tmp_path)
    assert _ids(c.get("/api/stations/search", params={"q": "prag"})) == ["p1"]
    assert _ids(c.get("/api/stations/search", params={"q": "cologne"})) == ["k1"]
    assert _ids(c.get("/api/stations/search", params={"q": "koeln"})) == ["k1"]


def test_search_exonym_prefix_while_typing(tmp_path):
    c = _exonym_client(tmp_path)
    # "vien" is a prefix of the exonym "vienna" -> must already find Wien
    assert _ids(c.get("/api/stations/search", params={"q": "vien"})) == ["w1"]


@pytest.mark.parametrize(("query", "station_id"), [
    ("rome", "r1"),
    ("copenhagen", "c1"),
    ("the hague", "h1"),
    ("bucharest", "bu1"),
    ("lodz", "l1"),
])
def test_search_new_english_exonyms(tmp_path, query, station_id):
    c = _exonym_client(tmp_path)
    assert _ids(c.get("/api/stations/search", params={"q": query})) == [station_id]


def test_search_copenhagen_exonym_prefix_while_typing(tmp_path):
    c = _exonym_client(tmp_path)
    assert _ids(c.get("/api/stations/search", params={"q": "copen"})) == ["c1"]


def test_search_native_names_unaffected(tmp_path):
    c = _exonym_client(tmp_path)
    assert _ids(c.get("/api/stations/search", params={"q": "praha"})) == ["p1"]
    assert _ids(c.get("/api/stations/search", params={"q": "wien"})) == ["w1"]
    assert _ids(c.get("/api/stations/search", params={"q": "roma"})) == ["r1"]
    assert _ids(c.get("/api/stations/search", params={"q": "københavn"})) == ["c1"]
    assert _ids(c.get("/api/stations/search", params={"q": "den haag"})) == ["h1"]
    assert _ids(c.get("/api/stations/search", params={"q": "bucurești"})) == ["bu1"]
    assert _ids(c.get("/api/stations/search", params={"q": "łódź"})) == ["l1"]
