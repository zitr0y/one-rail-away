# Trainline Results Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "Search on Trainline" opens Trainline's search results for the selected stations and the chosen date.

**Architecture:** The pipeline downloads Trainline's open `stations.csv` and matches our stations to Trainline location ids, writing `out/trainline_ids.json` into the data slot. A new FastAPI endpoint `/api/book` looks both stations up, builds the results URL (optionally wrapped in an affiliate prefix from env), logs the click and 302-redirects; anything unmatched or invalid falls back to the Trainline homepage. The web client just links to `/api/book` with the date picker's value.

**Tech Stack:** Python 3 (stdlib `csv`, `unicodedata`, `zoneinfo`), httpx, FastAPI + TestClient, pytest; React + TypeScript + vitest.

**Spec:** `docs/superpowers/specs/2026-09-23-trainline-results-handoff-design.md`

**Commands:** Python tests: `uv run pytest <path> -q` (repo root). Web tests: `cd web && npx vitest run <path>`. Known pre-existing failures: 5 in `tests/test_international.py` (hardcoded July DB ids, backlog AD) — ignore them.

---

## File structure

| File | Responsibility |
|---|---|
| `pipeline/trainline.py` (new) | Load Trainline candidates from CSV; match our stations to Trainline ids. Pure, no I/O besides reading the CSV. |
| `pipeline/fetch.py` | + `fetch_trainline_stations()` — download CSV, keep previous copy on failure. |
| `pipeline/cli.py` | `fetch` stage also calls `fetch_trainline_stations`. |
| `pipeline/compute.py` | `compute_all` writes `out/trainline_ids.json`. |
| `server/booking.py` (new) | Pure `booking_target()` — builds the redirect URL. |
| `server/app.py` | `/api/book` endpoint + cached `trainline_ids.json` read + click log. |
| `web/src/lib/booking.ts` | `bookingUrl(fromId, toId, date)` → `/api/book?...`. |
| `web/src/components/TripDetails.tsx` | Pass ids + date to `bookingUrl`. |
| `web/src/components/Map.tsx` | Attribution credit for Trainline stations (ODbL). |
| `docs/data-sources.md` | Record the new source + licence. |

---

### Task 1: Station matcher (`pipeline/trainline.py`)

**Goal:** Pure functions that load Trainline candidates and map our station ids to Trainline ids.

**Files:**
- Create: `pipeline/trainline.py`
- Test: `tests/test_trainline.py`

**Acceptance Criteria:**
- [ ] Name match (accent/punctuation-insensitive, equal or contains either way, min 4 chars for containment) within 5 km wins, nearest first
- [ ] Coordinate fallback: nearest candidate within 500 m
- [ ] Names containing `(Gr)` never match
- [ ] Rows without coordinates or with `is_suggestable != "t"` are ignored
- [ ] Missing CSV → `load_candidates` returns `[]`

**Verify:** `uv run pytest tests/test_trainline.py -q` → all pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trainline.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_trainline.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.trainline'`

- [ ] **Step 3: Implement**

```python
# pipeline/trainline.py
"""Match our stations to Trainline location ids (booking handoff, backlog N).

Source: https://github.com/trainline-eu/stations (`stations.csv`, `;`-separated,
ODbL-1.0). Only the id is used: `/api/book` turns a pair of ids into a
Trainline search-results URL.
"""

import csv
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

NAME_RADIUS_KM = 5.0
COORD_RADIUS_KM = 0.5
MIN_CONTAINS_LEN = 4
_CELL = 0.1  # degrees; +-1 cell north-south and +-2 east-west covers >= 5 km up to ~70°N


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    lat: float
    lon: float


def normalize_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())


def load_candidates(path: Path) -> list[Candidate]:
    """Searchable Trainline stations with coordinates; [] if the file is missing."""
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            if row.get("is_suggestable") != "t" or not row.get("latitude") or not row.get("longitude"):
                continue
            out.append(Candidate(row["id"], row["name"], float(row["latitude"]), float(row["longitude"])))
    return out


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dx = (lon2 - lon1) * 111.32 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 110.57
    return math.hypot(dx, dy)


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return (math.floor(lat / _CELL), math.floor(lon / _CELL))


def _names_match(ours: str, theirs: str) -> bool:
    if ours == theirs:
        return True
    if min(len(ours), len(theirs)) < MIN_CONTAINS_LEN:
        return False
    return ours in theirs or theirs in ours


def match_stations(
    stations: list[tuple[str, str, float, float]], candidates: list[Candidate]
) -> dict[str, str]:
    """{our id: trainline id} for `(id, name, lat, lon)` stations that match."""
    grid: dict[tuple[int, int], list[Candidate]] = defaultdict(list)
    for c in candidates:
        grid[_cell(c.lat, c.lon)].append(c)
    normalized = {c.id: normalize_name(c.name) for c in candidates}

    ids: dict[str, str] = {}
    for sid, name, lat, lon in stations:
        if "(Gr)" in name:
            continue
        ci, cj = _cell(lat, lon)
        nearby = sorted(
            ((_km(lat, lon, c.lat, c.lon), c)
             for di in (-1, 0, 1) for dj in (-2, -1, 0, 1, 2) for c in grid[(ci + di, cj + dj)]),
            key=lambda t: t[0],
        )
        ours = normalize_name(name)
        named = [c for d, c in nearby if d <= NAME_RADIUS_KM and _names_match(ours, normalized[c.id])]
        if named:
            ids[sid] = named[0].id
        elif nearby and nearby[0][0] <= COORD_RADIUS_KM:
            ids[sid] = nearby[0][1].id
    return ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_trainline.py -q`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/trainline.py tests/test_trainline.py
git commit -m "feat(pipeline): match stations to Trainline location ids (N)"
```

---

### Task 2: Fetch Trainline `stations.csv`

**Goal:** `ose fetch` also downloads the Trainline CSV to `data/raw/trainline_stations.csv`, keeping the previous copy on failure.

**Files:**
- Modify: `pipeline/fetch.py` (append function)
- Modify: `pipeline/cli.py:36-40` (`_run_fetch`)
- Test: `tests/test_fetch.py` (append)

**Acceptance Criteria:**
- [ ] Success writes the file and returns True
- [ ] HTTP error returns False, logs, and leaves an existing file untouched
- [ ] `_run_fetch` calls it after `fetch_all`

**Verify:** `uv run pytest tests/test_fetch.py tests/test_cli.py -q` → all pass

**Steps:**

- [ ] **Step 1: Write the failing tests** (append to `tests/test_fetch.py`)

```python
from pipeline.fetch import TRAINLINE_STATIONS_URL, fetch_trainline_stations


def test_fetch_trainline_stations_writes_file(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == TRAINLINE_STATIONS_URL
        return httpx.Response(200, content=b"id;name\n1;A\n")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_trainline_stations(tmp_path, client) is True
    assert (tmp_path / "trainline_stations.csv").read_bytes() == b"id;name\n1;A\n"


def test_fetch_trainline_stations_keeps_previous_on_failure(tmp_path):
    (tmp_path / "trainline_stations.csv").write_bytes(b"old")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    assert fetch_trainline_stations(tmp_path, client) is False
    assert (tmp_path / "trainline_stations.csv").read_bytes() == b"old"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_fetch.py -q`
Expected: FAIL — `ImportError: cannot import name 'TRAINLINE_STATIONS_URL'`

- [ ] **Step 3: Implement** (append to `pipeline/fetch.py`)

```python
TRAINLINE_STATIONS_URL = (
    "https://raw.githubusercontent.com/trainline-eu/stations/master/stations.csv"
)


def fetch_trainline_stations(raw_dir: Path, client: httpx.Client | None = None) -> bool:
    """Download Trainline's open stations.csv (ODbL) to raw_dir/trainline_stations.csv.

    Used only to map stations to Trainline ids for the booking handoff. On
    failure the previous copy (if any) is kept and the run continues.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    client = client or httpx.Client(timeout=120, follow_redirects=True)
    try:
        resp = client.get(TRAINLINE_STATIONS_URL)
        resp.raise_for_status()
        tmp = raw_dir / "trainline_stations.csv.tmp"
        tmp.write_bytes(resp.content)
        tmp.replace(raw_dir / "trainline_stations.csv")
        logger.info("fetched trainline stations (%d bytes)", len(resp.content))
        return True
    except Exception as exc:  # never abort the pipeline over the booking lookup
        logger.error("failed to fetch trainline stations: %s", exc)
        return False
    finally:
        if own_client:
            client.close()
```

In `pipeline/cli.py`, replace `_run_fetch` with:

```python
def _run_fetch(args: argparse.Namespace) -> None:
    from pipeline.config import load_feeds
    from pipeline.fetch import fetch_all, fetch_trainline_stations

    fetch_all(load_feeds(Path("feeds.toml")), RAW)
    fetch_trainline_stations(RAW)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_fetch.py tests/test_cli.py -q`
Expected: all pass (`tests/test_cli.py` does not exercise `_run_fetch`, so no network call happens).

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch.py pipeline/cli.py tests/test_fetch.py
git commit -m "feat(pipeline): fetch Trainline open stations.csv (N)"
```

---

### Task 3: Write `out/trainline_ids.json` in compute

**Goal:** `compute_all` writes the id mapping into the output slot and logs the match rate.

**Files:**
- Modify: `pipeline/compute.py` (`compute_all` signature ~line 351, and after the `stations.json` write ~line 433)
- Test: `tests/test_compute.py` (append)

**Acceptance Criteria:**
- [ ] `compute_all(..., trainline_csv=path)` writes `out_dir/trainline_ids.json` mapping station ids to Trainline ids
- [ ] Missing CSV → writes `{}` and prints a warning; compute still succeeds
- [ ] Prints `trainline: matched N/M stations`

**Verify:** `uv run pytest tests/test_compute.py -q` → all pass

**Steps:**

- [ ] **Step 1: Write the failing tests.** `tests/test_compute.py` already imports `json`, `date`, `build`, `compute_all`, `make_fixture_feeds`, `_write_feeds_toml` and `empty_overrides`. Append:

```python
def _built_graph(tmp):
    raw = tmp / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp)
    feeds_toml = _write_feeds_toml(tmp, cfgs)
    build(raw, tmp / "graph", feeds_toml, None, date(2026, 7, 14),
          station_names_path=names_toml, station_countries_path=countries_toml)
    return tmp / "graph", feeds_toml


def test_compute_writes_trainline_ids(tmp_path, capsys):
    graph_dir, feeds_toml = _built_graph(tmp_path)
    stations = json.loads((graph_dir / "stations.json").read_text())["stations"]
    first = stations[0]
    csv_path = tmp_path / "trainline_stations.csv"
    csv_path.write_text(
        "id;name;latitude;longitude;is_suggestable\n"
        f"4242;{first['name']};{first['lat']};{first['lon']};t\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    compute_all(graph_dir, out_dir, workers=1, feeds_path=feeds_toml, trainline_csv=csv_path)
    ids = json.loads((out_dir / "trainline_ids.json").read_text())
    assert ids[first["id"]] == "4242"
    assert "trainline: matched" in capsys.readouterr().out


def test_compute_trainline_ids_empty_without_csv(tmp_path):
    graph_dir, feeds_toml = _built_graph(tmp_path)
    out_dir = tmp_path / "out"
    compute_all(graph_dir, out_dir, workers=1, feeds_path=feeds_toml,
                trainline_csv=tmp_path / "missing.csv")
    assert json.loads((out_dir / "trainline_ids.json").read_text()) == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_compute.py -q -k trainline`
Expected: FAIL — `TypeError: compute_all() got an unexpected keyword argument 'trainline_csv'`

- [ ] **Step 3: Implement.** In `pipeline/compute.py`, add the parameter to `compute_all` after `capitals_path`:

```python
    capitals_path: Path = Path("capitals.toml"),
    trainline_csv: Path = Path("data/raw/trainline_stations.csv"),
) -> None:
```

Add the import at the top with the other `pipeline` imports:

```python
from pipeline.trainline import load_candidates, match_stations
```

Directly after the `(out_dir / "stations.json").write_text(...)` block, add:

```python
    # Booking handoff (backlog N): our ids -> Trainline location ids, per slot,
    # so it always agrees with this slot's station ids.
    candidates = load_candidates(trainline_csv)
    if not candidates:
        print(f"WARNING trainline: no candidates in {trainline_csv}; Book falls back to the homepage")
    trainline_ids = match_stations([(s.id, s.name, s.lat, s.lon) for s in stations], candidates)
    print(f"trainline: matched {len(trainline_ids)}/{len(stations)} stations")
    (out_dir / "trainline_ids.json").write_text(json.dumps(trainline_ids))
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_compute.py tests/test_server.py -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add pipeline/compute.py tests/test_compute.py
git commit -m "feat(pipeline): write trainline_ids.json per data slot (N)"
```

---

### Task 4: `/api/book` redirect

**Goal:** Server endpoint that redirects to Trainline results (or homepage), with optional affiliate prefix and a click log line.

**Files:**
- Create: `server/booking.py`
- Modify: `server/app.py` (cache helper next to `_cached_stations` ~line 88; route inside `create_app` before `return app`)
- Test: `tests/test_booking.py` (new, pure function), `tests/test_server.py` (append, endpoint)

**Acceptance Criteria:**
- [ ] Matched ids + valid future-or-today date → results URL with all spec params
- [ ] Unmatched id, malformed date, or past date → `https://www.thetrainline.com/`
- [ ] `TRAINLINE_LINK_PREFIX` set → `prefix + quote(target, safe="")`
- [ ] Endpoint answers 302 and prints `BOOK from=… to=… date=… matched=…`
- [ ] Missing `trainline_ids.json` → homepage, never 5xx

**Verify:** `uv run pytest tests/test_booking.py tests/test_server.py -q` → all pass

**Steps:**

- [ ] **Step 1: Write the failing pure-function tests**

```python
# tests/test_booking.py
from datetime import date
from urllib.parse import parse_qs, urlsplit

from server.booking import HOMEPAGE, booking_target

IDS = {"x:berlin": "7630", "x:munich": "7480"}
TODAY = date(2026, 9, 23)


def test_matched_pair_builds_results_url():
    url, matched = booking_target("x:berlin", "x:munich", "2026-09-29", IDS, TODAY, "")
    assert matched is True
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://www.thetrainline.com/book/results"
    q = parse_qs(parts.query)
    assert q["journeySearchType"] == ["single"]
    assert q["origin"] == ["urn:trainline:generic:loc:7630"]
    assert q["destination"] == ["urn:trainline:generic:loc:7480"]
    assert q["outwardDate"] == ["2026-09-29T06:00:00"]
    assert q["outwardDateType"] == ["departAfter"]
    assert q["selectedTab"] == ["train"]
    assert q["passengers[]"] == ["1996-01-01"]


def test_today_is_allowed():
    _, matched = booking_target("x:berlin", "x:munich", "2026-09-23", IDS, TODAY, "")
    assert matched is True


def test_unmatched_station_falls_back_to_homepage():
    assert booking_target("x:berlin", "x:nowhere", "2026-09-29", IDS, TODAY, "") == (HOMEPAGE, False)


def test_past_date_falls_back_to_homepage():
    assert booking_target("x:berlin", "x:munich", "2026-09-22", IDS, TODAY, "") == (HOMEPAGE, False)


def test_malformed_date_falls_back_to_homepage():
    assert booking_target("x:berlin", "x:munich", "29.09.2026", IDS, TODAY, "") == (HOMEPAGE, False)


def test_prefix_wraps_and_encodes_target():
    url, _ = booking_target("x:berlin", "x:nowhere", "2026-09-29", IDS, TODAY,
                            "https://prf.hn/click/camref:ABC/destination:")
    assert url == "https://prf.hn/click/camref:ABC/destination:https%3A%2F%2Fwww.thetrainline.com%2F"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_booking.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.booking'`

- [ ] **Step 3: Implement `server/booking.py`**

```python
"""Trainline booking handoff target (backlog N).

The results-URL format is verified (2026-09-23) but not officially documented
by Trainline, so every failure path falls back to the homepage. Affiliate
tracking is a prefix supplied via env once Partnerize approves us; nothing
affiliate-related is hardcoded here.
"""

from datetime import date
from urllib.parse import quote, urlencode

HOMEPAGE = "https://www.thetrainline.com/"
RESULTS = "https://www.thetrainline.com/book/results"


def booking_target(
    from_id: str, to_id: str, date_str: str, ids: dict[str, str], today: date, prefix: str
) -> tuple[str, bool]:
    """(url to redirect to, whether it is a prefilled results search)."""
    origin, destination = ids.get(from_id), ids.get(to_id)
    try:
        travel = date.fromisoformat(date_str)
    except ValueError:
        travel = None
    matched = bool(origin and destination and travel and travel >= today)
    if matched:
        target = RESULTS + "?" + urlencode({
            "journeySearchType": "single",
            "origin": f"urn:trainline:generic:loc:{origin}",
            "destination": f"urn:trainline:generic:loc:{destination}",
            "outwardDate": f"{travel.isoformat()}T06:00:00",
            "outwardDateType": "departAfter",
            "selectedTab": "train",
            # One adult; Trainline asks for a date of birth per passenger.
            "passengers[]": date(today.year - 30, 1, 1).isoformat(),
        })
    else:
        target = HOMEPAGE
    if prefix:
        target = prefix + quote(target, safe="")
    return target, matched
```

- [ ] **Step 4: Run pure tests**

Run: `uv run pytest tests/test_booking.py -q`
Expected: 6 passed

- [ ] **Step 5: Write the failing endpoint tests** (append to `tests/test_server.py`)

```python
def test_book_redirects_matched_pair_to_results(client, capsys):
    stations = client.get("/api/stations").json()["stations"]
    a, b = stations[0]["id"], stations[1]["id"]
    (client.data_dir / "trainline_ids.json").write_text(json.dumps({a: "7630", b: "7480"}))
    resp = client.get("/api/book", params={"from": a, "to": b, "date": "2099-01-05"},
                      follow_redirects=False)
    assert resp.status_code == 302
    assert "urn%3Atrainline%3Ageneric%3Aloc%3A7630" in resp.headers["location"]
    assert "outwardDate=2099-01-05T06%3A00%3A00" in resp.headers["location"]
    assert f"BOOK from={a} to={b} date=2099-01-05 matched=true" in capsys.readouterr().out


def test_book_unmatched_goes_to_homepage(client):
    (client.data_dir / "trainline_ids.json").write_text("{}")
    resp = client.get("/api/book", params={"from": "a", "to": "b", "date": "2099-01-05"},
                      follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://www.thetrainline.com/"


def test_book_without_mapping_file_goes_to_homepage(client):
    (client.data_dir / "trainline_ids.json").unlink(missing_ok=True)
    resp = client.get("/api/book", params={"from": "a", "to": "b", "date": "2099-01-05"},
                      follow_redirects=False)
    assert resp.headers["location"] == "https://www.thetrainline.com/"


def test_book_applies_link_prefix(client, monkeypatch):
    monkeypatch.setenv("TRAINLINE_LINK_PREFIX", "https://prf.hn/click/camref:ABC/destination:")
    (client.data_dir / "trainline_ids.json").write_text("{}")
    resp = client.get("/api/book", params={"from": "a", "to": "b", "date": "2099-01-05"},
                      follow_redirects=False)
    assert resp.headers["location"].startswith("https://prf.hn/click/camref:ABC/destination:https%3A")
```

Note: each test writes `trainline_ids.json` itself because the module-scoped `client` fixture is shared; the mtime cache must pick up rewrites (tests write different content — if two writes land in the same mtime tick the cache could serve stale data; the cache below keys on `(mtime_ns, size)` to make that practically impossible).

- [ ] **Step 6: Implement the endpoint.** In `server/app.py` add imports at the top:

```python
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from starlette.responses import RedirectResponse

from server.booking import booking_target
```

(`RedirectResponse` can join the existing `from starlette.responses import ...` line.)

Add after `_cached_stations`:

```python
_trainline_ids_cache: dict[Path, tuple[tuple[int, int], dict[str, str]]] = {}


def _cached_trainline_ids(data_dir: Path) -> dict[str, str]:
    """`trainline_ids.json` for the live slot; {} if the pipeline hasn't written one."""
    path = data_dir / "trainline_ids.json"
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {}
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _trainline_ids_cache.get(path)
    if cached is None or cached[0] != key:
        _trainline_ids_cache[path] = (key, json.loads(path.read_text(encoding="utf-8")))
    return _trainline_ids_cache[path][1]
```

Inside `create_app`, before `return app`:

```python
    @app.get("/api/book")
    def book(
        from_id: str = Query("", alias="from"),
        to_id: str = Query("", alias="to"),
        date: str = "",
    ) -> RedirectResponse:
        today = datetime.now(ZoneInfo("Europe/Berlin")).date()
        url, matched = booking_target(
            from_id, to_id, date, _cached_trainline_ids(data_dir), today,
            os.environ.get("TRAINLINE_LINK_PREFIX", ""),
        )
        # Click log (grep BOOK in `docker logs`): the traffic figure affiliate
        # programmes ask for.
        print(f"BOOK from={from_id} to={to_id} date={date} matched={str(matched).lower()}",
              flush=True)
        return RedirectResponse(url, status_code=302)
```

- [ ] **Step 7: Run to verify pass**

Run: `uv run pytest tests/test_booking.py tests/test_server.py -q`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add server/booking.py server/app.py tests/test_booking.py tests/test_server.py
git commit -m "feat(server): /api/book redirects to Trainline results (N)"
```

---

### Task 5: Web — link Book to `/api/book`, credit Trainline data

**Goal:** The Book button carries origin, destination and the picked date; the map credits the Trainline dataset.

**Files:**
- Modify: `web/src/lib/booking.ts` (`bookingUrl`, last function)
- Modify: `web/src/components/TripDetails.tsx:107`
- Modify: `web/src/components/Map.tsx:39-41` (`TIMETABLE_ATTRIBUTION`)
- Modify: `docs/data-sources.md` (geodata table, ~line 38)
- Test: `web/src/lib/booking.test.ts`, `web/src/components/TripDetails.test.tsx`

**Acceptance Criteria:**
- [ ] `bookingUrl("x:db_fern:1", "B", "2026-07-13")` → `/api/book?from=x%3Adb_fern%3A1&to=B&date=2026-07-13`
- [ ] TripDetails renders that href for the default date (tomorrow) and updates it when the date changes
- [ ] Attribution mentions "Stations: Trainline EU (ODbL)"
- [ ] `docs/data-sources.md` lists the dataset and its licence

**Verify:** `cd web && npx vitest run src/lib/booking.test.ts src/components/TripDetails.test.tsx src/components/Map.test.tsx && npx tsc --noEmit` → all pass, no type errors

**Steps:**

- [ ] **Step 1: Update tests.** In `web/src/lib/booking.test.ts` replace the first `it(...)` block with:

```ts
  it("links to the server-side Trainline redirect with ids and date", () => {
    expect(bookingUrl("x:db_fern:1", "B", "2026-07-13"))
      .toBe("/api/book?from=x%3Adb_fern%3A1&to=B&date=2026-07-13");
  });
```

In `web/src/components/TripDetails.test.tsx` line 40, replace
`expect(markup).toContain('href="https://www.thetrainline.com/"');` with:

```ts
    expect(markup).toContain('href="/api/book?from=A&amp;to=B&amp;date=2026-07-13"');
```

and add inside the `describe("TripDetails booking date", ...)` block:

```ts
  it("carries the picked date into the booking link", () => {
    const container = document.createElement("div");
    const root = createRoot(container);
    act(() => {
      root.render(<TripDetails origin={origin} destination={destination} dest={dest}
                               maxTrains={2} stationsById={stationsById} />);
    });
    act(() => {
      container.querySelector<HTMLButtonElement>('[aria-label="Next day"]')!.click();
    });
    expect(container.querySelector<HTMLAnchorElement>("a.book")!.getAttribute("href"))
      .toBe("/api/book?from=A&to=B&date=2026-07-14");
    act(() => root.unmount());
  });
```

- [ ] **Step 2: Run to verify failure**

Run: `cd web && npx vitest run src/lib/booking.test.ts src/components/TripDetails.test.tsx`
Expected: FAIL — `bookingUrl` returns the homepage; href mismatch

- [ ] **Step 3: Implement.** In `web/src/lib/booking.ts` replace `bookingUrl` with:

```ts
// The server resolves our station ids to Trainline ids and redirects to the
// search results (or the Trainline homepage when it can't). See /api/book.
export function bookingUrl(fromId: string, toId: string, date: string): string {
  return `/api/book?${new URLSearchParams({ from: fromId, to: toId, date })}`;
}
```

In `web/src/components/TripDetails.tsx:107` change `href={bookingUrl()}` to:

```tsx
      <a className="book" href={bookingUrl(origin.id, destination.id, bookingDate)}
```

In `web/src/components/Map.tsx:39-41`:

```ts
const TIMETABLE_ATTRIBUTION =
  "Timetables: DB · SNCF · ÖBB · SBB · NS · Rejseplanen · FlixTrain · " +
  "CP – Comboios de Portugal · Trenitalia · Renfe · PKP PLK · " +
  "Stations: Trainline EU (ODbL)";
```

In `docs/data-sources.md`, add a row to the "In use — geodata" table:

```markdown
| **Trainline EU stations** (`github.com/trainline-eu/stations`, `stations.csv`) | Mapping our stations to Trainline ids for the Book button (`trainline_ids.json`) | ODbL 1.0 — attribution in the map credits |
```

- [ ] **Step 4: Run to verify pass**

Run: `cd web && npx vitest run && npx tsc --noEmit`
Expected: all pass (if `Map.test.tsx` asserts the exact attribution string, update it to the new constant)

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/booking.ts web/src/lib/booking.test.ts web/src/components/TripDetails.tsx web/src/components/TripDetails.test.tsx web/src/components/Map.tsx docs/data-sources.md
git commit -m "feat(web): Book opens Trainline results for the picked date (N)"
```

---

### Task 6: Full suite, local end-to-end, deploy

**Goal:** Everything green locally, then live on onestopeurope.eu with a real click-through.

**Files:** none (verification + deploy). Deploy only after the user confirms.

**Acceptance Criteria:**
- [ ] `uv run pytest -q` passes except the 5 known `test_international.py` failures
- [ ] Local: generate `trainline_ids.json` against a real data slot and hit `/api/book` for Berlin Hbf → München Hbf; `Location` is a results URL
- [ ] After deploy + recompute on the server: Book for Berlin Hbf → München Hbf lands on Trainline results for the picked date in a real browser; an unmatched station lands on the homepage; `docker logs aaron-trains-api | grep BOOK` shows the clicks

**Verify:** `curl -sI "https://onestopeurope.eu/api/book?from=<berlin id>&to=<munich id>&date=<tomorrow>" | grep -i location` → `https://www.thetrainline.com/book/results?...loc%3A7630...loc%3A7480...`

**Steps:**

- [ ] **Step 1:** `uv run pytest -q` and `cd web && npx vitest run && npx tsc --noEmit`.
- [ ] **Step 2 (local e2e):** copy the live `stations.json` into a scratch dir, run the matcher against a freshly fetched CSV, start `uvicorn server.app:create_app --factory` pointed at that dir (or reuse the existing dev setup from the `verify` skill), and `curl -sI` `/api/book` for the Berlin Hbf and München Hbf ids from that `stations.json`.
- [ ] **Step 3 (ask user first):** deploy with `scripts/deploy.sh` on the server (code), then run `fetch` + `compute` so the live slot gains `trainline_ids.json` (`build` is not needed — ids derive from the existing graph). Check the log line `trainline: matched N/M`.
- [ ] **Step 4:** Real-browser click-through (Playwright text read, no screenshots) + `curl` check above + `docker logs aaron-trains-api | grep -c BOOK`.
- [ ] **Step 5:** Update backlog N in `docs/superpowers/feedback-backlog.md` from "in progress" to shipped with the date and match rate; commit.
