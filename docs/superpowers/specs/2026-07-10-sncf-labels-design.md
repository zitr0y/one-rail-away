# SNCF train labels (brand + train number) — design

Date: 2026-07-10. Approved by user in brainstorming session.
Investigation evidence: `.superpowers/sdd/sncf-labels-findings.md` (2026-07-09, verified
against the real 2026-07 export).

## Problem

SNCF journey legs display opaque route codes ("802A") because the feed's
`route_short_name` is an internal line code and `route_long_name` is unreliable
(empty/junk for OUIGO and night Intercités). The real train identity lives in
`trip_headsign` (100% populated, 100% numeric across all 50,977 trips) plus the brand
word embedded in the per-brand `StopPoint:OCE<brand>-…` stop ids.

## Behavior (user decisions)

SNCF legs show official sub-brands + train number:

| stop id pattern | brand word | example label |
|---|---|---|
| `^StopPoint:OCETGV INOUI-` | `TGV INOUI` | TGV INOUI 9704 |
| `^StopPoint:OCEOUIGO-` | `OUIGO` | OUIGO 7871 |
| `^StopPoint:OCEICE-` | `ICE` | ICE 9552 |
| `^StopPoint:OCELyria-` | `TGV Lyria` | TGV Lyria 9203 |
| `^StopPoint:OCEINTERCITES-` | `Intercités` | Intercités 3921 |
| `^StopPoint:OCEINTERCITES de nuit-` | `Intercités de nuit` | Intercités de nuit 5771 |
| `^StopPoint:OCETrain-` | `IC` | IC 50 |

- "TGV Lyria" (not "Lyria"), "TGV INOUI" (not "TGV") — official sub-brands, user's call.
- `OCETrain-` is the classic-line Paris↔Bruxelles service (via Aulnoye-Aymeries,
  train numbers 50–69, verified in the feed) — labeled `IC`, user's call.
- The two INTERCITES patterns cannot cross-match: each requires a hyphen immediately
  after its brand string.
- No web changes; labels flow through the reach/trip data files.

## Approach (chosen)

Considered: (A) config-driven `stop_id_brand` table that also acts as the trip filter;
(B) regex on route names — rejected, long names are junk for OUIGO/night-Intercités;
(C) hardcoded sncf branch in gtfs.py — rejected, breaks the config-driven filter
pattern. **Chosen: A.**

## Architecture

- **`pipeline/config.py`**: `FeedConfig` gains optional `stop_id_brand: dict[str, str]`
  (regex pattern → brand word). Validation: a feed setting BOTH `stop_id_brand` and
  `stop_id_allow` is a config error (one source of truth for the stop-id filter).
- **`feeds.toml`**: sncf's `stop_id_allow` list is replaced by a `stop_id_brand` table
  with the 7 mappings above. Evidence comments preserved and extended (they are
  load-bearing, per project convention).
- **`pipeline/gtfs.py`** (`load_feed`):
  - Read `trip_headsign` in the trips pass.
  - When `stop_id_brand` is set, its patterns act as the stop-id trip filter with the
    same semantics and per-stop-id verdict caching as `stop_id_allow` today.
  - Kept trip's label = `f"{brand} {trip_headsign}"`, where brand comes from the
    trip's first stop (stop_sequence order) that matches a brand pattern, patterns
    checked in config table order for determinism.
  - Empty headsign → fall back to the current route-name label (never expected to
    fire — 100% headsign coverage — but prevents `"TGV INOUI "` from a feed quirk).
  - Brand resolution is factored as a small pure helper (unit-testable without zip
    fixtures).

## Join safety (critical trap)

`pipeline/through.py` joins cross-feed trips on exact label match + digit; relabeling
SNCF can change join behavior. Baseline: 201 joined border segments, ZERO touching
SNCF. Protocol:

1. Record baseline join count from the current build log/data before changing anything.
2. Rebuild; diff join counts. New SNCF-touching joins are acceptable only after
   inspection confirms they are real through-trains (e.g. SNCF "ICE 9552" now matching
   db_fern's label at the border). Any drop below baseline elsewhere = failure, stop.
3. `tests/test_international.py` must stay green (locked-in regression suite).
4. Build validation (SystemExit on unmerged duplicates) remains the stop-the-line net:
   validation failures = STOP and report, never improvise in merge code.

## Execution

- `uv run ose build` (~4 min, foreground) then `uv run ose compute` (~15–20 min,
  background, wait for notification — do not poll).
- Spot checks on fresh data: a Paris reach file shows `TGV INOUI`/`OUIGO`/… leg labels;
  no SNCF leg label matches the opaque `^\d{3}[A-Z]$` code shape.

## Testing

- TDD throughout. Unit tests: brand-resolution helper (match, table-order determinism,
  empty-headsign fallback, no-match); config: `stop_id_brand` parses, both-fields
  rejection, and regression assertions that the real sncf patterns match/reject
  example stop ids (mirroring the existing sbb route_allow regression test).
- Full suite (108 pytest) green before review; join-count diff recorded in the task
  report.
