# SNCF Train Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SNCF journey legs show real train identities ("TGV INOUI 9704", "OUIGO 7871") instead of opaque route codes ("802A").

**Architecture:** A new optional `FeedConfig.stop_id_brand` table (regex pattern → brand word) replaces sncf's `stop_id_allow`: its patterns act as the stop-id trip filter, and each kept trip is relabeled `"<brand> <trip_headsign>"`. Brand resolution is a pure helper in `pipeline/gtfs.py`. A full pipeline re-run regenerates the data; through-join counts are diffed before/after because joins match on exact labels.

**Tech Stack:** Python 3.14 (uv-only — `uv run …`, never pip/venv), pydantic v2, pytest, TOML config.

Spec: `docs/superpowers/specs/2026-07-10-sncf-labels-design.md` (approved 2026-07-10).

## Global Constraints

- Branch: create `sncf-labels` off `main` (Task 1 does this; later tasks stay on it).
- Brand table (exact values, user decisions): `^StopPoint:OCETGV INOUI-` → `TGV INOUI`, `^StopPoint:OCEOUIGO-` → `OUIGO`, `^StopPoint:OCEICE-` → `ICE`, `^StopPoint:OCELyria-` → `TGV Lyria`, `^StopPoint:OCEINTERCITES-` → `Intercités`, `^StopPoint:OCEINTERCITES de nuit-` → `Intercités de nuit`, `^StopPoint:OCETrain-` → `IC`.
- A feed setting BOTH `stop_id_allow` and `stop_id_brand` is a config error.
- Empty `trip_headsign` → keep the current route-name label (no `"TGV INOUI "` labels).
- Join-safety baseline (verified live 2026-07-10 on current `data/graph/trips.json`): 5059 trips, **201 join events, 0 SNCF-touching**. After rebuild: non-SNCF join events must stay exactly 201; new SNCF-touching joins are acceptable only if listed and inspected; any drop = STOP and report.
- Build validation failures (`SystemExit(1)` on unmerged duplicates) = STOP and report, never improvise in merge code.
- Evidence comments in `feeds.toml` are load-bearing — preserve and extend them.
- Python style: ruff, line length 100. Run pytest via `uv run pytest`.
- `uv run ose build` ~4 min (foreground, 600000 ms timeout). `uv run ose compute` ~15–20 min (background; WAIT for completion notification, do not poll).

---

### Task 1: `FeedConfig.stop_id_brand` + mutual-exclusion validation

**Files:**
- Modify: `pipeline/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (Tasks 2–3 rely on these): `FeedConfig.stop_id_brand: dict[str, str] | None = None` (regex pattern → brand word, insertion-ordered); constructing a `FeedConfig` with both `stop_id_allow` and `stop_id_brand` raises a pydantic `ValidationError` whose message contains "not both".

- [ ] **Step 1: Create the branch**

```bash
git checkout main && git checkout -b sncf-labels
```

- [ ] **Step 2: Write the failing tests**

In `tests/test_config.py`: add `import pytest` to the imports at the TOP of the file (next to `import re`) and change the pipeline import to `from pipeline.config import FeedConfig, load_feeds` — ruff rejects imports appended mid-file. Then append the tests:

```python
def test_stop_id_brand_accepts_pattern_to_brand_table():
    cfg = FeedConfig(
        url="u", country="XX", license="t", route_allow=["."],
        stop_id_brand={"^SP:OCETGV INOUI-": "TGV INOUI"},
    )
    assert cfg.stop_id_brand == {"^SP:OCETGV INOUI-": "TGV INOUI"}


def test_stop_id_brand_and_stop_id_allow_are_mutually_exclusive():
    # Both fields drive the same stop-id trip filter; two sources of truth would
    # let them silently disagree.
    with pytest.raises(ValueError, match="not both"):
        FeedConfig(
            url="u", country="XX", license="t", route_allow=["."],
            stop_id_allow=["^SP:"], stop_id_brand={"^SP:": "TGV"},
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: the two new tests FAIL (`stop_id_brand` is not a `FeedConfig` field — pydantic rejects the unknown kwarg or the validator is missing); the two existing tests still PASS.

- [ ] **Step 4: Implement**

In `pipeline/config.py`: change the pydantic import and add the field + validator to `FeedConfig` (after `stop_id_allow`, before `uic_regex`):

```python
from pydantic import BaseModel, model_validator
```

```python
    # Optional stop-id brand table: regex pattern -> brand word. When set, the
    # patterns act as the stop-id trip filter (same semantics as stop_id_allow)
    # AND each kept trip is relabeled "<brand> <trip_headsign>". Needed for the
    # SNCF combined export: the commercial brand lives only in per-brand stop
    # ids and the train number only in trip_headsign (route_short_name is an
    # opaque line code like "802A").
    stop_id_brand: dict[str, str] | None = None
    uic_regex: str | None = None  # extracts UIC code from stop_id

    @model_validator(mode="after")
    def _single_stop_id_filter(self) -> "FeedConfig":
        if self.stop_id_allow and self.stop_id_brand:
            raise ValueError("set stop_id_allow or stop_id_brand, not both")
        return self
```

(`uic_regex` shown for placement only — it already exists; don't duplicate it.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: all 4 PASS.

- [ ] **Step 6: Lint and commit**

```bash
uv run ruff check pipeline/config.py tests/test_config.py
git add pipeline/config.py tests/test_config.py
git commit -m "feat: FeedConfig.stop_id_brand table (filter + brand labeling, exclusive with stop_id_allow)"
```

---

### Task 2: Brand labeling in `load_feed`

**Files:**
- Modify: `pipeline/gtfs.py`
- Test: `tests/test_gtfs.py`

**Interfaces:**
- Consumes (Task 1): `FeedConfig.stop_id_brand: dict[str, str] | None`.
- Produces: `pipeline.gtfs._brand_label(stop_ids: Iterable[str], brand_patterns: list[tuple[re.Pattern[str], str]], headsign: str) -> str | None`; `load_feed` labels stop_id_brand-filtered trips `"<brand> <headsign>"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gtfs.py` (add `import re` to its imports; `_make_feed`, `CFG`, `SAMPLE`, `FeedConfig`, `load_feed` already exist in the file — also extend the gtfs import to `from pipeline.gtfs import _brand_label, load_feed, next_tuesday`):

```python
# --- stop-id brand labeling (SNCF) ---------------------------------------------


def test_brand_label_first_matching_stop_wins_in_sequence_order():
    patterns = [(re.compile("^A-"), "Alpha"), (re.compile("^B-"), "Beta")]
    # First stop matches nothing, second matches the SECOND pattern: the first
    # MATCHING STOP decides (not the first pattern with any match anywhere).
    assert _brand_label(["X-1", "B-2", "A-3"], patterns, "42") == "Beta 42"
    assert _brand_label(["X-1"], patterns, "42") is None  # no brand stop
    assert _brand_label(["A-1"], patterns, "") is None  # empty headsign


def test_stop_id_brand_filters_and_labels_brand_plus_headsign(tmp_path):
    # SNCF: the brand lives only in per-brand StopPoint ids and the train number
    # only in trip_headsign. stop_id_brand's patterns act as the stop-id trip
    # filter AND relabel each kept trip "<brand> <trip_headsign>".
    cfg = FeedConfig(
        url="u", country="XX", license="t", route_allow=["."],
        stop_id_brand={"^SP:OCETGV INOUI-": "TGV INOUI", "^SP:OCEOUIGO-": "OUIGO"},
    )
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "SP:OCETGV INOUI-1,Alpha,50.0,8.0\n"
            "SP:OCETGV INOUI-2,Beta,50.0,9.0\n"
            "SP:OCEOUIGO-1,Alpha,50.0,8.0\n"
            "SP:OCEOUIGO-3,Gamma,50.1,8.1\n"
            "SP:OCETER-1,Alpha,50.0,8.0\n"
            "SP:OCETER-3,Gamma,50.1,8.1\n"
        ),
        routes_txt="route_id,route_short_name,route_type\nR1,001G,2\nR2,C30,2\nR3,C31,2\n",
        trips_txt=(
            "route_id,service_id,trip_id,trip_headsign\n"
            "R1,S1,T1,9704\n"
            "R2,S1,T2,7871\n"
            "R3,S1,T3,4402\n"  # TER stops only: filtered out
        ),
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,SP:OCETGV INOUI-1,1\n"
            "T1,09:00:00,09:00:00,SP:OCETGV INOUI-2,2\n"
            "T2,07:00:00,07:00:00,SP:OCEOUIGO-1,1\n"
            "T2,07:30:00,07:30:00,SP:OCEOUIGO-3,2\n"
            "T3,07:00:00,07:00:00,SP:OCETER-1,1\n"
            "T3,07:30:00,07:30:00,SP:OCETER-3,2\n"
        ),
    )
    _, trips = load_feed(zip_path, cfg, SAMPLE)
    assert {t.trip_id: t.train for t in trips} == {"T1": "TGV INOUI 9704", "T2": "OUIGO 7871"}


def test_stop_id_brand_empty_headsign_falls_back_to_route_label(tmp_path):
    # 100% headsign coverage in the real export, but a feed quirk must not
    # produce a dangling "TGV INOUI " label.
    cfg = FeedConfig(
        url="u", country="XX", license="t", route_allow=["."],
        stop_id_brand={"^SP:OCETGV-": "TGV INOUI"},
    )
    zip_path = _make_feed(
        tmp_path,
        stops_txt=(
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "SP:OCETGV-1,Alpha,50.0,8.0\n"
            "SP:OCETGV-2,Beta,50.0,9.0\n"
        ),
        routes_txt="route_id,route_short_name,route_type\nR1,001G,2\n",
        trips_txt="route_id,service_id,trip_id,trip_headsign\nR1,S1,T1,\n",
        stop_times_txt=(
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "T1,08:00:00,08:00:00,SP:OCETGV-1,1\n"
            "T1,09:00:00,09:00:00,SP:OCETGV-2,2\n"
        ),
    )
    _, trips = load_feed(zip_path, cfg, SAMPLE)
    (trip,) = trips
    assert trip.train == "001G"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_gtfs.py -v -k brand`
Expected: FAIL — `ImportError: cannot import name '_brand_label'`.

- [ ] **Step 3: Implement**

In `pipeline/gtfs.py`:

(a) Extend the collections import:

```python
from collections.abc import Iterable, Iterator
```

(b) Add the pure helper directly above `load_feed`:

```python
def _brand_label(
    stop_ids: Iterable[str],
    brand_patterns: list[tuple[re.Pattern[str], str]],
    headsign: str,
) -> str | None:
    """Brand+number label ("TGV INOUI 9704"), or None to keep the route label.

    The brand comes from the first stop id (stop-sequence order) that matches
    any brand pattern, patterns checked in config table order. An empty
    headsign yields None: "TGV INOUI " would be worse than the opaque code.
    """
    if not headsign:
        return None
    for sid in stop_ids:
        for pattern, brand in brand_patterns:
            if pattern.search(sid):
                return f"{brand} {headsign}"
    return None
```

(c) In `load_feed`, replace the current `stop_id_allow` compilation block

```python
    stop_id_allow = (
        [re.compile(p) for p in cfg.stop_id_allow] if cfg.stop_id_allow else None
    )
```

with:

```python
    brand_patterns = (
        [(re.compile(p), b) for p, b in cfg.stop_id_brand.items()]
        if cfg.stop_id_brand
        else None
    )
    if cfg.stop_id_allow:
        stop_id_allow = [re.compile(p) for p in cfg.stop_id_allow]
    elif brand_patterns:
        # stop_id_brand doubles as the stop-id trip filter (config forbids both).
        stop_id_allow = [p for p, _ in brand_patterns]
    else:
        stop_id_allow = None
```

(d) In the trips pass, capture headsigns for brand-labeled feeds. The loop currently ends with:

```python
            else:
                trip_train[t["trip_id"]] = routes[t["route_id"]]
```

Append after that if/else (still inside the `for t in _rows(zf, "trips.txt")` loop; `trip_headsign` is declared next to `trip_train`):

```python
        trip_headsign: dict[str, str] = {}
```

```python
            if brand_patterns is not None and t["trip_id"] in trip_train:
                trip_headsign[t["trip_id"]] = (t.get("trip_headsign") or "").strip()
```

(e) In the kept-trips loop, relabel BEFORE parent resolution (the brand lives in the RAW stop ids; `_resolve` rewrites `s.station` in place). The loop currently reads:

```python
            if stop_id_allow is not None and not any(_stop_id_passes(s.station) for s in kept):
                continue
            for s in kept:
```

Insert between the `continue` and the `for s in kept:`:

```python
            if brand_patterns is not None:
                # Brand also lives in the RAW ids: label before parent resolution.
                label = _brand_label(
                    (s.station for s in kept), brand_patterns, trip_headsign.get(tid, "")
                )
                if label is not None:
                    trip_train[tid] = label
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_gtfs.py -v`
Expected: all PASS (3 new + all existing).

- [ ] **Step 5: Full suite, lint, commit**

```bash
uv run pytest
uv run ruff check pipeline/ tests/
git add pipeline/gtfs.py tests/test_gtfs.py
git commit -m "feat: brand+headsign trip labels for stop_id_brand feeds"
```

Expected: 108+5 = 113 pytest passed, ruff clean.

---

### Task 3: Switch sncf to `stop_id_brand` in feeds.toml

**Files:**
- Modify: `feeds.toml` (repo root — the `[feeds.sncf]` section)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes (Tasks 1–2): `stop_id_brand` parsing + filter/label semantics.
- Produces: the live sncf config Task 4 rebuilds with.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py` (`re` and `Path` are already imported there):

```python
def test_sncf_stop_id_brand_matches_real_brand_stop_ids():
    """SNCF marks brands only in StopPoint ids; the train number is in trip_headsign.
    These patterns both filter trips and label them (design 2026-07-10)."""
    feeds = load_feeds(Path("feeds.toml"))
    assert feeds["sncf"].stop_id_allow is None  # replaced by stop_id_brand
    table = feeds["sncf"].stop_id_brand

    def brand_for(stop_id):  # mirrors gtfs._brand_label: first pattern match wins
        for pattern, brand in table.items():
            if re.search(pattern, stop_id):
                return brand
        return None

    assert brand_for("StopPoint:OCETGV INOUI-87686006") == "TGV INOUI"
    assert brand_for("StopPoint:OCEOUIGO-87686006") == "OUIGO"
    assert brand_for("StopPoint:OCEICE-87113001") == "ICE"
    assert brand_for("StopPoint:OCELyria-87686006") == "TGV Lyria"
    assert brand_for("StopPoint:OCEINTERCITES-87547000") == "Intercités"
    # "de nuit" must NOT be captured by the plain INTERCITES pattern: each
    # pattern requires a hyphen immediately after its brand string.
    assert brand_for("StopPoint:OCEINTERCITES de nuit-87547000") == "Intercités de nuit"
    assert brand_for("StopPoint:OCETrain-87271007") == "IC"
    # TER and road coaches stay excluded ("Train TER" has a space, not a hyphen).
    assert brand_for("StopPoint:OCETrain TER-87271007") is None
    assert brand_for("StopPoint:OCECar TER-87271007") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: the new test FAILS (`stop_id_allow` is still set / `stop_id_brand` is None).

- [ ] **Step 3: Edit feeds.toml**

In `[feeds.sncf]`, delete the `stop_id_allow = [ … ]` list (keep every comment above it — they are load-bearing evidence). At the END of the sncf section (after the "No uic_regex" comment block, immediately before `[feeds.oebb]`), add:

```toml
# stop_id_brand doubles as the stop-id trip filter (same semantics as the old
# stop_id_allow list) and relabels each kept trip "<brand> <trip_headsign>".
# trip_headsign is 100% populated and numeric in this export (all 50,977 trips,
# verified 2026-07-09); route_short_name stays an opaque line code ("802A").
# Brand words are the official sub-brands (user decision 2026-07-10).
# "OCETrain-" is the classic-line Paris-Bruxelles corridor (via Aulnoye-Aymeries,
# train numbers 50-69, verified in the 2026-07 export): labeled "IC".
# "Train TER"/"Car TER" cannot match: every pattern requires "-" right after the
# brand, TER ids have " TER" there.
[feeds.sncf.stop_id_brand]
"^StopPoint:OCETGV INOUI-" = "TGV INOUI"
"^StopPoint:OCEOUIGO-" = "OUIGO"
"^StopPoint:OCEICE-" = "ICE"
"^StopPoint:OCELyria-" = "TGV Lyria"
"^StopPoint:OCEINTERCITES-" = "Intercités"
"^StopPoint:OCEINTERCITES de nuit-" = "Intercités de nuit"
"^StopPoint:OCETrain-" = "IC"
```

Also update the pre-existing comment above `route_allow` that says "stop_id_allow selects trips by brand" to say "stop_id_brand selects trips by brand (and labels them)".

TOML gotcha: `[feeds.sncf.stop_id_brand]` is a sub-table of `[feeds.sncf]`; it MUST come after all plain `key = value` lines of `[feeds.sncf]` and before `[feeds.oebb]`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: all PASS.

- [ ] **Step 5: Full suite, commit**

```bash
uv run pytest
git add feeds.toml tests/test_config.py
git commit -m "feat: SNCF brand labels via stop_id_brand (TGV INOUI/OUIGO/Lyria/Intercités/ICE/IC)"
```

Expected: 114 passed.

---

### Task 4: Rebuild, join-safety diff, recompute, refresh tracked samples

**Files:**
- Modify (regenerated): `data/graph/*` (git-ignored), `data/out/*` (git-ignored except the 7 force-added samples: `meta.json`, `stations.json`, 5 `reach_x:db_fern:*.json`)

**Interfaces:**
- Consumes: Tasks 1–3 merged state on the branch.
- Produces: fresh data files served by the API; verification evidence in the task report.

- [ ] **Step 1: Verify the baseline on the CURRENT (pre-rebuild) data**

```bash
python3 - <<'EOF'
import json
trips = json.load(open("data/graph/trips.json"))["trips"]
print("trips:", len(trips),
      "| join events:", sum(t["trip_id"].count("+") for t in trips),
      "| sncf-touching:", sum(t["trip_id"].count("+") for t in trips if "OCESN" in t["trip_id"]))
EOF
```

Expected output: `trips: 5059 | join events: 201 | sncf-touching: 0`. Record it in the report. If it differs, STOP and report (stale data assumption).

- [ ] **Step 2: Rebuild the graph**

Run: `uv run ose build` (foreground, 600000 ms timeout, ~4 min).
Expected: completes with exit 0. If it exits via SystemExit(1) validation (unmerged duplicates), STOP and report the duplicate list verbatim — do not touch merge code or aliases.

- [ ] **Step 3: Join-safety diff + label check on the new graph**

```bash
python3 - <<'EOF'
import json, re
trips = json.load(open("data/graph/trips.json"))["trips"]
joins = sum(t["trip_id"].count("+") for t in trips)
sncf_joins = [t for t in trips if "+" in t["trip_id"] and "OCESN" in t["trip_id"]]
non_sncf_joins = joins - sum(t["trip_id"].count("+") for t in sncf_joins)
sncf = [t for t in trips if t["trip_id"].startswith("OCESN")]
opaque = sorted({t["train"] for t in sncf if re.fullmatch(r"\d{3}[A-Z]", t["train"])})
brands = {}
for t in sncf:
    brands[t["train"].rsplit(" ", 1)[0]] = brands.get(t["train"].rsplit(" ", 1)[0], 0) + 1
print("join events:", joins, "| non-sncf:", non_sncf_joins, "| sncf-touching:", len(sncf_joins))
for t in sncf_joins:
    print("  SNCF join:", t["train"], t["trip_id"][:80])
print("sncf trips:", len(sncf), "| opaque labels left:", opaque)
print("brand counts:", brands)
EOF
```

Pass criteria (all must hold, else STOP and report):
- `non-sncf` join events == 201 (the baseline — relabeling must not disturb non-SNCF joins).
- `opaque labels left` == `[]` (no `\d{3}[A-Z]` codes remain on SNCF trips).
- `brand counts` keys ⊆ {TGV INOUI, OUIGO, ICE, TGV Lyria, Intercités, Intercités de nuit, IC} with TGV INOUI the largest bucket (~500+ of ~735 SNCF trips).
- Any `SNCF join:` lines are new cross-feed through-joins: copy them into the report for controller inspection (do not decide their fate yourself).

- [ ] **Step 4: Regression suite on real data**

Run: `uv run pytest tests/test_international.py -v`
Expected: all PASS (locked-in international regressions — Berlin/Wien/Zürich cases).

- [ ] **Step 5: Recompute reach files**

Run: `uv run ose compute` in the background (~15–20 min) and WAIT for its completion notification — do not poll.
Expected: exit 0, ~1144 reach files regenerated in `data/out/`.

- [ ] **Step 6: Spot-check branded labels in reach files**

```bash
python3 - <<'EOF'
import glob, json, re
branded, opaque = 0, set()
for f in glob.glob("data/out/reach_*.json"):
    for dest in json.load(open(f))["destinations"]:
        for j in dest["journeys"]:
            for leg in j["legs"]:
                if re.fullmatch(r"\d{3}[A-Z]", leg["train"]):
                    opaque.add(leg["train"])
                if leg["train"].startswith(("TGV", "OUIGO", "Intercités")):
                    branded += 1
print("branded SNCF legs:", branded, "| opaque leg labels:", sorted(opaque))
EOF
```

Expected: `branded SNCF legs:` in the thousands; `opaque leg labels: []`. (If the reach JSON schema differs — e.g. key names — read `web/src/lib/types.ts` for the real shape and adapt the scan, not the criteria.)

- [ ] **Step 7: Refresh the force-added samples and commit**

```bash
uv run pytest && uv run ruff check pipeline/ tests/
git add -f data/out/meta.json data/out/stations.json "data/out/reach_x:db_fern:127002.json" \
  "data/out/reach_x:db_fern:296593.json" "data/out/reach_x:db_fern:365732.json" \
  "data/out/reach_x:db_fern:490623.json" "data/out/reach_x:db_fern:569849.json"
git commit -m "data: rebuild with SNCF brand labels; refresh tracked samples"
```

Expected: full suite green (114), ruff clean. The report must include: baseline vs post-rebuild join numbers, any SNCF-join lines, brand counts, and the reach-file spot-check output.
