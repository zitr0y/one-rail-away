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
    ]
    (tmp_path / "stations.json").write_text(json.dumps({"stations": stations}))
    return TestClient(create_app(tmp_path))


def test_normalize_strips_accents():
    assert normalize("München") == "munchen"
    assert normalize("Zürich HB") == "zurich hb"


def test_search_prefix_beats_substring_and_skips_no_reach(tmp_path):
    got = _client(tmp_path).get("/api/stations/search", params={"q": "munchen"}).json()["stations"]
    names = [s["name"] for s in got]
    assert names[0] == "München Hbf"  # prefix + shortest
    assert "Bad München-Dorf" in names  # substring still found
    assert all(s["id"] != "4" for s in got)  # has_reach=False excluded
