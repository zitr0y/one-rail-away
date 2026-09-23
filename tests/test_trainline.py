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


def test_normalize_name_folds_letters_nfkd_keeps():
    assert normalize_name("Kraków Główny") == "krakowglowny"
    assert normalize_name("Øresund ÆßŒı Đ") == "oresundaessoeid"


def test_polish_station_matches_station_not_city():
    cands = [
        Candidate("29325", "Kraków", 50.068338, 19.945266),
        Candidate("17584", "Kraków Główny", 50.067192, 19.947423),
    ]
    ids = match_stations([("x:k", "Krakow Glowny", 50.067196, 19.947426)], cands)
    assert ids == {"x:k": "17584"}


def test_exact_name_beats_closer_containment():
    cands = [
        Candidate("1", "Lindau Hbf Insel", 47.5450, 9.6800),   # ~100 m, containment
        Candidate("2", "Lindau Hbf", 47.5630, 9.6800),         # ~2 km, exact
    ]
    ids = match_stations([("x:l", "Lindau Hbf", 47.5441, 9.6800)], cands)
    assert ids == {"x:l": "2"}


def test_load_candidates_unparsable_latitude_returns_empty(tmp_path, caplog):
    path = _csv(tmp_path, ["7630;Berlin Hbf;berlin-hbf;;;abc;13.369548;;t"])
    assert load_candidates(path) == []
    assert "trainline" in caplog.text.lower()


def test_load_candidates_missing_id_column_returns_empty(tmp_path):
    path = tmp_path / "stations.csv"
    path.write_text("name;latitude;longitude;is_suggestable\nBerlin;52.5;13.4;t\n",
                    encoding="utf-8")
    assert load_candidates(path) == []


def test_match_stations_reports_breakdown():
    cands = [
        Candidate("7630", "Berlin Hbf", 52.5256, 13.3695),
        Candidate("17509", "Praha hl.n.", 50.0831, 14.4353),
    ]
    stats: dict[str, int] = {}
    ids = match_stations([
        ("a", "Berlin Hbf", 52.5256, 13.3695),
        ("b", "Praha Hauptbahnhof", 50.0840, 14.4360),
        ("c", "Flensburg(Gr)", 54.7743, 9.4367),
    ], cands, stats=stats)
    assert ids == {"a": "7630", "b": "17509"}
    assert stats == {"name": 1, "coord": 1, "border": 1}
