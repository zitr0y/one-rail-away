# UIC Merge-Gap Fix Implementation Plan (backlog G)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An unknown UIC code falls back to the existing proximity+name check before minting
itself as a canonical station, so future feeds' shared stations auto-merge instead of each
needing a manual `station_aliases.toml` entry.

**Architecture:** One behavior change inside `pipeline/merge.py::merge_stations` pass 1, plus a
run-local `uic_aliases` dict (UIC code → canonical id) so later feeds carrying an already
fallback-merged code land on the same station deterministically. Zero canonical-id churn:
existing aliases stay, first-registered station keeps its id/name/coords/country. Spec (user
approved 2026-07-10): `docs/superpowers/specs/2026-07-10-uic-merge-gap-design.md`.

**Tech Stack:** Python 3 (uv-only), pytest, ruff.

## Global Constraints

- Python runs via `uv run …` only — never pip/venv/plain python.
- ruff clean, line length 100.
- TDD: failing test before implementation; commit after every task.
- Validation failures (`SystemExit(1)` from build) = STOP and report. Never improvise in
  merge code.
- Evidence-based comments for data/config changes (dates, counts, real station names).
- Expected no-op on current data: build validation is clean today, so the rebuilt
  `data/graph` must be byte-identical. Any diff = STOP and report.
- Subagent models: opus or sonnet only, never haiku.

---

### Task 1: UIC fallback in merge.py (code + tests + in-file docs)

**Files:**
- Modify: `pipeline/merge.py` (module docstring lines 7-13 and 34-39 area; pass-1 body
  currently lines 140-167; new helper next to `_uic_match`)
- Modify: `station_aliases.toml` (header comment, lines 1-9)
- Test: `tests/test_merge.py` (append new test section)

**Interfaces:**
- Consumes: existing `merge_stations(per_feed, aliases)`, `_norm`, `_dist_m`, `_uic_match`,
  `PROXIMITY_M` — all already in `pipeline/merge.py`.
- Produces: `merge_stations` signature and return type UNCHANGED. New module-private helper
  `_proximity_match(registry: dict[str, Station], name: str, lat: float, lon: float) -> str | None`.
  No other task imports anything new.

- [ ] **Step 1: Write the new tests (append to `tests/test_merge.py`)**

Append this section at the end of the file. Note the existing helpers at the top of the file:
`_cfg(**kw)` builds a `FeedConfig` (no `uic_regex` unless passed), `RawStop(stop_id, name, lat, lon)`.

```python
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
```

- [ ] **Step 2: Run the new tests, verify the expected RED/GREEN split**

Run: `uv run pytest tests/test_merge.py -v -k "fallback_merge or mints or onto"`

Expected: `test_uic_stop_merges_onto_existing_non_uic_station`,
`test_same_uic_code_from_third_feed_follows_fallback_merge`, and
`test_uic_stop_merges_onto_different_uic_canonical` FAIL (today a UIC match is terminal —
assertion errors like `len(stations) == 1` being 2). The other three
(`..._far_from_same_name...`, `..._near_different_name...`, `test_alias_beats_uic_fallback_merge`)
PASS already — they are regression guards pinning the behavior that must NOT change. If any
guard test fails, the test itself is wrong: fix the test, not the code.

- [ ] **Step 3: Implement — extract the proximity scan into a helper**

In `pipeline/merge.py`, add after `_uic_match` (before `merge_stations`):

```python
def _proximity_match(
    registry: dict[str, Station], name: str, lat: float, lon: float
) -> str | None:
    """First registered station <PROXIMITY_M away whose name normalizes equal.

    "First" is registry insertion order -- the documented feed-priority signal
    (#5) -- matching the behavior the inline scan had before extraction.
    """
    norm = _norm(name)
    return next(
        (
            sid
            for sid, s in registry.items()
            if _norm(s.name) == norm and _dist_m(s.lat, s.lon, lat, lon) < PROXIMITY_M
        ),
        None,
    )
```

- [ ] **Step 4: Implement — the UIC fallback in pass 1**

In `merge_stations`, add the `uic_aliases` dict right after the `stubs` declaration
(currently line 136):

```python
    stubs: list[tuple[str, str, str, FeedConfig]] = []  # (feed, stop_id, name, cfg)
    uic_aliases: dict[str, str] = {}  # UIC code -> canonical, from fallback merges (#7)
```

Then replace the canonical-resolution block (currently lines 146-158):

```python
            canonical = aliases.get(f"{feed}:{stop.stop_id}")
            if canonical is None:
                canonical = _uic_match(uic_re, stop.stop_id)
            if canonical is None:
                canonical = next(
                    (
                        sid
                        for sid, s in registry.items()
                        if _norm(s.name) == _norm(stop.name)
                        and _dist_m(s.lat, s.lon, stop.lat, stop.lon) < PROXIMITY_M
                    ),
                    None,
                ) or f"x:{feed}:{stop.stop_id}"
```

with:

```python
            canonical = aliases.get(f"{feed}:{stop.stop_id}")
            if canonical is None:
                code = _uic_match(uic_re, stop.stop_id)
                if code is not None:
                    if code in registry or code in uic_aliases:
                        canonical = uic_aliases.get(code, code)
                    else:
                        # Unknown code: run the same proximity+name check as
                        # rule 3 before minting it as canonical (#7).
                        near = _proximity_match(registry, stop.name, stop.lat, stop.lon)
                        if near is not None:
                            uic_aliases[code] = near
                        canonical = near or code
            if canonical is None:
                canonical = _proximity_match(
                    registry, stop.name, stop.lat, stop.lon
                ) or f"x:{feed}:{stop.stop_id}"
```

- [ ] **Step 5: Update the module docstring**

In `pipeline/merge.py`'s module docstring, replace the precedence item 2 line pair:

```
  2. UIC regex       -- cfg.uic_regex extracts a UIC code from the stop_id
```

with:

```
  2. UIC regex       -- cfg.uic_regex extracts a UIC code from the stop_id; a
                        known code merges onto its station, an UNKNOWN code first
                        falls back to the rule-3 proximity check (#7)
```

and append this paragraph at the end of the docstring (after the `#6` paragraph):

```
UIC fallback (#7, 2026-07-10): a UIC-extracted stop used to become canonical
immediately, so it could never proximity-merge onto a station already registered
under a non-UIC id (every sncf StopArea:OCE.../db_fern internal id) -- each
collision needed a manual station_aliases.toml entry (Konstanz, Mulhouse,
Frasne). Now an unknown code first runs the same proximity+name check as rule 3;
on a hit the code is recorded in a run-local uic_aliases map so every later feed
carrying the same code lands on the same station regardless of its coordinates
or spelling, and on a miss the code is minted as canonical exactly as before.
The fallback may merge onto a DIFFERENT UIC canonical (dual-code border
stations; symmetric with rule 3 -- user decision 2026-07-10). Cross-language
name twins ("Sarrebruck" vs "Saarbruecken Hbf") do not normalize equal and
still need explicit aliases.
```

- [ ] **Step 6: Update the `station_aliases.toml` header**

Insert between the "wrong merge that automatic rules cannot resolve." paragraph and the
`# Format:` line:

```toml
#
# Since 2026-07-10 (backlog G, merge.py rule #7) an unknown UIC code falls back
# to the same proximity+name check as other stops before minting itself as
# canonical, so most same-name UIC-vs-non-UIC collisions below would now merge
# automatically. The entries are KEPT deliberately: removing one would re-key
# its canonical id (first-registered id wins), silently regressing anything
# keyed by the old id (station_countries.toml overrides -- Konstanz precedent).
# Cross-language name twins ("Sarrebruck" vs "Saarbruecken Hbf") still need
# aliases -- the fallback requires normalized-name equality.
```

- [ ] **Step 7: Run the merge tests, then the full suite**

Run: `uv run pytest tests/test_merge.py -v`
Expected: all pass (existing tests + 6 new).

Run: `uv run pytest`
Expected: 122 passed (116 existing + 6 new), 0 failures.

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean. (Line length 100 — the fallback block above fits.)

- [ ] **Step 8: Commit**

```bash
git add pipeline/merge.py tests/test_merge.py station_aliases.toml
git commit -m "feat: UIC codes fall back to proximity+name before minting (backlog G)"
```

---

### Task 2: End-to-end no-op verification (rebuild + diff)

**Files:**
- No source changes. Reads `data/graph/stations.json`, `data/graph/trips.json`; rebuild
  rewrites them in place.

**Interfaces:**
- Consumes: Task 1's merged `pipeline/merge.py` (behavior change under test end-to-end).
- Produces: evidence (recorded in the task report) that the fallback is a no-op on current
  feeds. No artifacts for later tasks.

Rationale: build validation is clean today, meaning no unmerged same-normalized-name <500 m
pairs exist — so the new fallback must change NOTHING in the current graph. This task proves
it byte-for-byte. Raw GTFS zips already live in `data/raw` (do NOT run `ose fetch`).

- [ ] **Step 1: Snapshot the current graph**

```bash
TMP=$(mktemp -d)
cp data/graph/stations.json data/graph/trips.json "$TMP/"
echo "$TMP"
```

Expected: prints the snapshot dir. Keep the value for Step 3.

- [ ] **Step 2: Rebuild the graph**

Run: `uv run ose build` in the foreground with a 600000 ms timeout (~4 min).

Expected in output:
- NO `VALIDATION:` lines and no `SystemExit` — if validation fails, STOP and report
  verbatim; do not improvise fixes.
- `joined 201 border-split trip segments` (through-join count unchanged).
- Final line `graph: 1148 stations, 5059 trips -> data/graph` (counts measured from the
  current graph 2026-07-10). Any other numbers mean the fallback changed current merges —
  Step 3's diff will show what; report both counts.

- [ ] **Step 3: Diff against the snapshot**

```bash
diff -q "$TMP/stations.json" data/graph/stations.json
diff -q "$TMP/trips.json" data/graph/trips.json
```

Expected: no output from either (byte-identical). This confirms the no-op — recompute and
sample refresh are NOT needed, and there is nothing to commit.

If either file differs: STOP and report. Show `diff` stats and a jq summary of station-id
set differences:

```bash
jq -r '.stations[].id' "$TMP/stations.json" | sort > "$TMP/ids-before"
jq -r '.stations[].id' data/graph/stations.json | sort > "$TMP/ids-after"
diff "$TMP/ids-before" "$TMP/ids-after"
```

A diff means the fallback re-merged something in the CURRENT data, which contradicts clean
validation and needs human review before anything else happens.

- [ ] **Step 4: Re-run the full suite as a final gate**

Run: `uv run pytest` — Expected: 122 passed.
Run: `uv run ruff check .` — Expected: clean.

No commit in this task (nothing changed on disk if Step 3 passed).

---

### Task 3: Mark backlog items G and H done

**Files:**
- Modify: `docs/superpowers/feedback-backlog.md` (sections G at lines ~98-109 and H at
  lines ~111-120)

**Interfaces:**
- Consumes: nothing from other tasks (docs only; do this task LAST — it asserts work that
  Tasks 1-2 must have finished and verified).
- Produces: nothing consumed by code.

- [ ] **Step 1: Replace section G**

Replace the entire `## G. Merge-logic gap: ...` section (heading + body, up to but not
including `## H.`) with:

```markdown
## G. Merge-logic gap: UIC stops never proximity-merge — DONE 2026-07-10

Fixed in `pipeline/merge.py` (rule #7): an unknown UIC code now falls back to the
same proximity+name check as other stops before minting itself as canonical, with
a run-local `uic_aliases` map so later feeds carrying the same code follow the
merge deterministically. Symmetric UIC-vs-UIC merging included (dual-code border
stations). Zero id churn: existing `station_aliases.toml` entries kept on purpose
(removing one re-keys its canonical id — Konstanz/`station_countries.toml` trap).
Verified a byte-identical no-op rebuild on current feeds; the payoff is backlog A
(new feeds need ~no manual aliases). Known limit: cross-language name twins
("Sarrebruck" vs "Saarbrücken Hbf") still need aliases.
Spec: `docs/superpowers/specs/2026-07-10-uic-merge-gap-design.md`.
```

- [ ] **Step 2: Replace section H**

Replace the entire `## H. Cheap FR coverage win: ...` section (heading + body, up to but
not including `## I.`) with:

```markdown
## H. Cheap FR coverage win: SNCF Intercités — DONE (verified 2026-07-10)

Already shipped as a side effect of the SNCF labels task (merge f9ca9f1): sncf
`route_allow = ["."]` with the `stop_id_brand` table selecting and labeling
INTERCITES / INTERCITES de nuit — 72 Intercités + 15 night trips live in the
2026-07-10 data. The "stops must merge cleanly" prerequisite is item G (done,
see above). Reminder kept: Intercités also appear inside the Swiss feed
(agency 87_LEX, "IC190A") — never ingest them from there; provenance belongs
with SNCF (see the sbb route_allow evidence comments in feeds.toml).
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/feedback-backlog.md
git commit -m "docs: backlog — G (UIC merge fallback) done, H verified already shipped"
```
