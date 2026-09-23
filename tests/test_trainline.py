from pipeline.trainline import Candidate, load_candidates, match_stations, normalize_name

HEADER = "id;name;slug;uic;uic8_sncf;latitude;longitude;parent_station_id;is_suggestable\n"


def _csv(tmp_path, rows: list[str]):
    path = tmp_path / "stations.csv"
    path.write_text(HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")
    return path


def test_normalize_name_strips_accents_and_punctuation():
    assert normalize_name("München Hbf") == "munchenhbf"
    assert normalize_name("Praha hl.n.") == "prahahln"


def test_load_candidates_skips_unsuggestable_and_coordinate_less(tmp_path):
    path = _csv(tmp_path, [
        "7630;Berlin Hbf;berlin-hbf;8065969;;52.525589;13.369548;;t",
        "1;Hidden;hidden;;;52.5;13.4;;f",
        "2;No Coords;no-coords;;;;;;t",
    ])
    assert [c.id for c in load_candidates(path)] == ["7630"]


def test_load_candidates_missing_file(tmp_path):
    assert load_candidates(tmp_path / "nope.csv") == []


def test_name_match_within_5km_beats_closer_other_name():
    cands = [
        Candidate("9", "Somewhere Else", 52.5260, 13.3700),   # ~50 m away, wrong name
        Candidate("7630", "Berlin Hbf", 52.5300, 13.3700),    # ~500 m away, right name
    ]
    ids = match_stations([("x:1", "Berlin Hbf", 52.5256, 13.3695)], cands)
    assert ids == {"x:1": "7630"}


def test_name_match_is_accent_insensitive_and_contains():
    cands = [Candidate("7480", "München Hbf", 48.1402, 11.5583)]
    ids = match_stations([("x:2", "Munchen Hbf (tief)", 48.1410, 11.5590)], cands)
    assert ids == {"x:2": "7480"}


def test_same_name_20km_away_is_rejected():
    cands = [Candidate("5", "Neustadt", 50.0, 10.0)]
    assert match_stations([("x:3", "Neustadt", 50.18, 10.0)], cands) == {}


def test_coordinate_fallback_within_500m():
    cands = [Candidate("17509", "Praha hl.n.", 50.0831, 14.4353)]
    ids = match_stations([("x:4", "Praha Hauptbahnhof", 50.0840, 14.4360)], cands)
    assert ids == {"x:4": "17509"}


def test_coordinate_fallback_rejects_beyond_500m():
    cands = [Candidate("17509", "Praha hl.n.", 50.0831, 14.4353)]
    assert match_stations([("x:5", "Other", 50.0900, 14.4353)], cands) == {}


def test_border_points_never_match():
    cands = [Candidate("8", "Flensburg", 54.7743, 9.4367)]
    assert match_stations([("x:6", "Flensburg(Gr)", 54.7743, 9.4367)], cands) == {}


def test_short_names_need_exact_match():
    # "Au" must not match "Aurich" by containment.
    cands = [Candidate("3", "Aurich", 47.0, 9.0)]
    assert match_stations([("x:7", "Au", 47.0, 9.02)], cands) == {}
