# München Ostbahnhof Rename and München City Group Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename 'Ostbahnhof' to 'München Ostbahnhof' and group it with 'München Hbf' into a new 'München' city group in `cities.toml` (which matches post-rename names since renames happen before city matching in the pipeline). Add pytest coverage verifying the rename, city matching, and that Graz Ostbahnhof remains unaffected.

**Architecture:** Edit configuration files pipeline/station_names.toml and cities.toml. Add unit and integration tests to tests/test_build.py and tests/test_cities.py.

**Tech Stack:** Python, TOML, pytest

## Global Constraints

- Do not push commits.
- Run all tests before completing work.
- If a test fails, do NOT hack the implementation — stop and report.

---

### Task 1: Find Pipeline Order Verification
Verify whether renames in `pipeline/station_names.toml` are applied before or after `cities.toml` matching.
**Files:**
- Modify: None (pure research/documentation task)

- [ ] **Step 1: Document finding in plan and commit body**
We found that:
1. `pipeline/build.py` loads `station_names.toml` overrides and applies them to the `Station` objects in-memory.
2. The final station objects are then serialized to `data/out/stations.json`.
3. `pipeline/compute.py` loads `stations.json` and parses them back into `Station` objects.
4. `pipeline/compute.py` calls `load_cities(Path("cities.toml"), stations)`.
5. `pipeline/cities.py` matches members by exact name (`s.name`).
Therefore, name overrides from `station_names.toml` are applied BEFORE city matching.
This means the member name in `cities.toml` must be the post-rename name: `"München Ostbahnhof"`.

---

### Task 2: Rename 'Ostbahnhof' in pipeline/station_names.toml
**Files:**
- Modify: `pipeline/station_names.toml`

- [ ] **Step 1: Add rename to pipeline/station_names.toml**
Add the following entry under `[names]`:
```toml
# München Ostbahnhof: DB feed strips the city prefix (leaving "Ostbahnhof").
# The id is volatile (backlog AM). Verified still current 2026-07-16.
"x:db_fern:226810" = "München Ostbahnhof"
```

- [ ] **Step 2: Commit intermediate change**
Run `git status` and commit.

---

### Task 3: Add München City Group to cities.toml
**Files:**
- Modify: `cities.toml`

- [ ] **Step 1: Add München group to cities.toml**
Add the following entry under `[cities]`:
```toml
"München" = ["München Hbf", "München Ostbahnhof"]
```

- [ ] **Step 2: Commit intermediate change**
Run `git status` and commit.

---

### Task 4: Add and Extend Pytest Coverage
**Files:**
- Modify: `tests/test_build.py`
- Modify: `tests/test_cities.py`

- [ ] **Step 1: Add test in tests/test_build.py for rename and Graz Ostbahnhof**
Add a test `test_munchen_ostbahnhof_rename_does_not_affect_graz` in `tests/test_build.py` that verifies:
- `x:db_fern:226810` gets renamed to `München Ostbahnhof`.
- `x:oebb:Pat:46:3038` (Graz Ostbahnhof) remains unaffected.

- [ ] **Step 2: Add test in tests/test_cities.py for post-rename matching**
Extend/add a test `test_munchen_city_group_matches_post_rename` in `tests/test_cities.py` to assert that:
- A city group matches members by their post-rename names.

- [ ] **Step 3: Run pytest**
Run `.venv/bin/pytest -q` to make sure all tests pass.

- [ ] **Step 4: Commit all changes**
Run `git add` and commit with message:
```
feat(pipeline): rename München Ostbahnhof, add München city group (Z)

We verified that station name overrides in station_names.toml are applied in
build.py before compute.py loads the stations and resolves city groups via
cities.toml. Thus, city group matching happens on post-rename station names,
so the München group in cities.toml keys its member as 'München Ostbahnhof'.
```
