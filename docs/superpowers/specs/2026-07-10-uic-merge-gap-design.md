# UIC merge-gap fix — design (backlog item G)

**Date:** 2026-07-10
**Status:** approved by user (approach, UIC-vs-UIC policy, and all three design
sections confirmed in brainstorm)
**Backlog:** item G in `docs/superpowers/feedback-backlog.md`. Item H (SNCF
Intercités) was verified already shipped by the SNCF-labels work (`route_allow =
["."]` + `stop_id_brand` selects INTERCITES / INTERCITES de nuit; 72 + 15 trips
live) — nothing of H remains except this fix.

## Problem

In `pipeline/merge.py::merge_stations`, canonical-id precedence per stop is
alias → UIC regex → proximity+name → fresh `x:` id, and a UIC match is
**terminal**: when a stop's extracted UIC code is not yet registered, the code
is minted as a fresh canonical station without ever running the proximity+name
check. Any same physical station already registered under a non-UIC canonical
(all SNCF `StopArea:OCE…` ids, all db_fern internal ids) becomes a duplicate,
caught by build validation and resolved today by a manual
`station_aliases.toml` entry (Konstanz, Mulhouse, Frasne, …).

**Goal (user decision):** future feeds need ~no manual aliases. This fix is the
prerequisite for backlog A (new national feeds) — a newly added feed's
border/shared stations should auto-merge. Existing canonical ids must stay
stable: zero id churn, no data re-keying.

## Rejected alternatives

- **SNCF `uic_regex` with check-digit stripping** (backlog option a): churns
  every SNCF canonical id (aliases, `station_countries.toml` keys, all reach
  files), fights `merge.py`'s deliberate digit-adjacency guard, and does nothing
  for db_fern-side collisions (Konstanz was db_fern vs sbb).
- **Post-merge auto-repair pass** (scan + retro-merge duplicates): usurps the
  validation step's role. Established convention: validation failures mean stop
  and report, never improvise in merge code.

## Design

### Algorithm change (`pipeline/merge.py`, pass 1 only)

Make the UIC step fall through when the code is unknown:

```
code = _uic_match(uic_re, stop_id)
if code is not None:
    if code in registry:            → merge onto it                    (unchanged)
    elif code in uic_aliases:       → merge onto uic_aliases[code]     (new)
    elif proximity+name hit S:      → merge onto S; uic_aliases[code] = S.id  (new)
    else:                           → mint code as canonical           (unchanged)
```

- `uic_aliases: dict[str, str]` (UIC code → canonical id) is a new run-local
  dict inside `merge_stations`. Once a code fallback-merges onto a station,
  every later feed carrying the same code lands on the same station
  deterministically — even if that feed's coordinates are >500 m off or its
  name spelling differs.
- The proximity scan reused is **literally the existing one**: same `_norm`
  normalization, same `PROXIMITY_M = 500`, same first-registered-match-wins
  semantics if several stations qualify (registry insertion order).
- **UIC-vs-UIC (user decision): merge symmetrically.** The fallback may match a
  station whose canonical is a *different* UIC code (dual-code border stations,
  e.g. FR `87…` vs CH `85…`). Existing step-3 proximity already merges non-UIC
  stops onto UIC canonicals under the same guards, so this is symmetric, with
  the identical risk profile.
- Everything else untouched: explicit aliases keep absolute precedence; the
  first registrant keeps display name / coords / country (documented
  determinism contract — feed order in `feeds.toml` is the priority signal);
  stub pass 2 unchanged (stubs never consult `uic_aliases`; YAGNI); insertion-
  order determinism preserved.

### What deliberately does NOT change

- **Existing `station_aliases.toml` entries stay**, even where the fallback
  makes them redundant. Removing them would re-key canonical ids (db_fern
  registers first, so Konstanz would flip from `8014586` to
  `x:db_fern:185018`) and silently regress the re-keyed
  `station_countries.toml` override — the known trap. The toml header is
  updated: the gap is fixed for *future* collisions; existing entries are kept
  for id stability.
- **Cross-language name twins still need aliases** ("Sarrebruck" vs
  "Saarbrücken Hbf" do not normalize equal) — documented as a known limit.
- **Validation stays the safety net**, unchanged (`SystemExit(1)` on unmerged
  duplicates). The fallback narrows what reaches it; it does not replace it.
- Interaction note: if a *future* explicit alias mints a UIC code as canonical
  after that code was fallback-merged elsewhere, validation flags the resulting
  near-duplicate — resolved by fixing the alias, as today.

### Documentation touched

`merge.py` module docstring (precedence list + fallback), `station_aliases.toml`
header, backlog item G marked done.

## Testing & verification

TDD in `tests/test_merge.py`:

1. UIC stop arriving after a same-normalized-name station <500 m away (non-UIC
   canonical) merges onto it; no new station; mapping correct.
2. Same code but >500 m away → mints the UIC canonical (unchanged behavior).
3. Same distance but different normalized name → mints.
4. A third feed with the same UIC code, offset coords / different spelling,
   still lands on the merged station via `uic_aliases`.
5. UIC stop merges onto a *different-UIC* canonical (symmetric case).
6. Explicit alias precedence unchanged.

Plus the full existing suite (116 pytest) green, ruff clean.

End-to-end: rebuild (`uv run ose build`) and **diff the station registry
against current** `data/graph`. Build validation is clean today (no unmerged
norm-equal <500 m pairs exist), so the fallback must be a provable no-op on
current feeds: expect an empty diff, and skip recompute if so. Belt-and-braces:
through-join count unchanged (201 joined segments).
