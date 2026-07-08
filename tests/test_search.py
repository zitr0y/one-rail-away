import json

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
