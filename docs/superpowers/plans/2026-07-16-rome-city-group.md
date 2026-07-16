# Rome City Group Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 'Roma' city group to cities.toml with comment annotations, confirm warning behavior on unmatched names, and add a pytest test for it.

**Architecture:** Modify `cities.toml` to add the "Roma" group and write a corresponding unit test in `tests/test_cities.py` to verify that the group resolves when matching stations exist and does not abort the build if they are unmatched.

**Tech Stack:** Python, TOML, pytest

## Global Constraints

- Do not push commits.
- Run all tests before completing work.
- If a test fails, do NOT hack the implementation — stop and report.

---

### Task 1: Add Rome City Group to cities.toml
**Files:**
- Modify: `cities.toml`

- [ ] **Step 1: Add Roma group to cities.toml**
Add the Roma group under `[cities]`:
```toml
# Roma: all-caps names come from the Trenitalia NeTEx feed (verified live 2026-07-16).
# 'Roma, Stazione di Roma Tiburtina' is an unmerged ÖBB duplicate of ROMA TIBURTINA (backlog AP) included so the union covers it.
"Roma" = ["ROMA TERMINI", "ROMA TIBURTINA", "ROMA OSTIENSE", "Roma, Stazione di Roma Tiburtina"]
```

---

### Task 2: Add Pytest Coverage
**Files:**
- Modify: `tests/test_cities.py`

- [ ] **Step 1: Add unit test in tests/test_cities.py**
Add `test_rome_city_group_resolves` to `tests/test_cities.py` that verifies:
- `Roma` group resolves to its members when they are defined.
- Unmatched names (as expected in local builds without the Trenitalia feed) produce a warning but do not abort.

- [ ] **Step 2: Run pytest**
Run `.venv/bin/pytest -q` to make sure all tests pass.

- [ ] **Step 3: Commit all changes**
Run `git add` and commit with message:
`feat(pipeline): Rome city group (AG)`
