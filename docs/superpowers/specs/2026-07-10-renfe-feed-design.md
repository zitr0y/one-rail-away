# Renfe feed ingestion — design (backlog A, feed 1 of N)

**Date:** 2026-07-10
**Status:** approved by user (batching, operator scope, first-country choice,
approach, TRENCELTA inclusion, station_names mechanism, and all three design
sections confirmed in brainstorm)
**Backlog:** item A in `docs/superpowers/feedback-backlog.md` ("Barcelona only
shows France"; Madrid/Porto unfindable).

## Decisions (user, 2026-07-10)

- **Batching:** one feed first to prove the post-G pattern, then batches of
  2-3. Spain is feed 1. Research verdicts for the rest (agy/Gemini web
  research, URLs HEAD-verified live): Poland MEDIUM (mkuran.pl community GTFS,
  CC0, UIC stop ids), Denmark MEDIUM (Rejseplanen official GTFS, UIC ids, big
  all-modes zip), Portugal HARD (rolling 7-10-day calendar), Italy HARD
  (NeTEx-only, Italo absent), Czechia HARD (NeTEx/CZPTT official, GTFS only
  Prague-regional), Hungary MEDIUM-HARD (GTFS behind corporate registration).
  Suggested batch 2: Poland + Denmark.
- **Operator scope:** ALL long-distance operators where a usable feed exists
  (incumbent + open-access). The Renfe feed carries only RENFE OPERADORA;
  Ouigo España / iryo get a bounded feed-existence check (below).
- **Display names:** new `pipeline/station_names.toml` override mechanism; fix
  the three French/shouty Spanish station labels.

## Evidence (real zip inspected 2026-07-10)

`https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip` (776 KB,
registration-free; the NAP detail page napt.mitma.es/Datasets/Detail/273
requires login). Single agency `1071 RENFE OPERADORA`. 1017 stops, 5-digit
internal stop ids (NOT UIC), `parent_station` hierarchy present, names carry
proper Spanish diacritics ("Madrid-Chamartín-Clara Campoamor" = 17000).
Calendar spans 2026-07-10..2026-12-08 — covers the sample date 2026-07-14.
Route products by `route_short_name` (row counts in routes.txt):

    136 MD, 110 REG.EXP., 102 REGIONAL, 77 AVE, 73 ALVIA, 51 Intercity,
    40 PROXIMDAD, 30 AVANT, 24 AVLO, 10 AVE INT, 7 EUROMED, 3 TRENCELTA,
    2 AVANT EXP

Despite the "AV_LD" name the zip includes regional products — filtering is
required. The feed also carries 7 French stops with good French names
(Marseille St Charles 87089, Montpellier Saint-Roch 87173, Narbonne 87088,
Perpignan 87374, Lyon Part Dieu 87303, …) and Portuguese stops from the
Vigo–Porto Tren Celta (Porto Campanha 94346, Viana do Castelo 94033).
License: Spanish public-sector reuse (Ley 37/2007 / RD 1495/2011,
data.renfe.com/legal) — reuse allowed with attribution "Renfe".

## Design

### 1. Feed entry (`feeds.toml`)

New `[feeds.renfe]` placed **LAST** (after `[feeds.ns]`). Position is
load-bearing: feed order is the name-ownership priority signal, and renfe must
NOT register first for the 7 French stations it carries (that would re-key
heavily-used SNCF canonicals over name variants like "St"/"Saint"). Spanish
stations it shares with SNCF leaks already have canonical ids that stay stable.

- `url` as above; `country = "ES"`; license line with attribution note.
- NO `uic_regex` (5-digit internal ids; evidence comment).
- `route_allow` matching exactly the long-distance products, anchored:
  `^AVE$`, `^AVE INT$`, `^ALVIA$`, `^AVLO$`, `^Intercity$`, `^EUROMED$`,
  `^TRENCELTA$`. Excluded (evidence comment): AVANT, AVANT EXP, MD, REGIONAL,
  REG.EXP., PROXIMDAD (medium-distance/commuter). TRENCELTA (Vigo–Porto
  cross-border, ~2.5 h) is IN by user decision — it puts Porto on the map.
- Evidence comments carry the product table and calendar span above, with the
  2026-07-10 inspection date.

The implementer verifies the matcher against how `route_allow` is applied
(both-names matching: `route_short_name` when set, else long name) and adjusts
anchoring to the actual mechanics — the product WORDS above are the contract.

### 2. Merging

- Girona (renfe 79300 "Girona" vs `x:sncf:StopArea:OCE71793000` "GIRONA") and
  Figueres-Vilafant (renfe 04307 vs `x:sncf:StopArea:OCE71043075`
  "FIGUERES-VILAFANT") normalize equal and sit <500 m — they merge via
  existing rule 3, no aliases.
- Barcelona-Sants does NOT normalize equal ("Barcelona" vs "Barcelone"):
  one alias `"renfe:71801" = "x:sncf:StopArea:OCE71718010"` with evidence
  comment.
- The 7 French stops merge onto existing SNCF canonicals where names
  normalize equal; any that don't are resolved by evidence-commented aliases
  when build validation flags them (the designed workflow — validation
  failures are worked through, never bypassed).
- Portuguese stops become new canonical stations; geographic country
  assignment gives them PT (no override expected).
- Renfe has two distinct Figueres stations (79309 classic-line "Figueres",
  04307 "Figueres-Vilafant" HS) — genuinely different stations, must NOT be
  merged with each other.

### 3. Display names (`pipeline/station_names.toml`, new)

Mechanism mirrors `station_countries.toml` exactly: lives in `pipeline/` next
to the code (same loading-trap comment), `[names]` table mapping canonical
station id → display name, applied in build after merge + country assignment.
An entry whose id doesn't exist in the registry must fail the build loudly —
align with whatever `station_countries.toml` does today (verify; if it is
silent, make BOTH loud, that staleness bit us before — Konstanz).
Entries (evidence-commented):

    "x:sncf:StopArea:OCE71718010" = "Barcelona-Sants"
    "x:sncf:StopArea:OCE71793000" = "Girona"
    "x:sncf:StopArea:OCE71043075" = "Figueres-Vilafant"

Server `EXONYMS` flips `"barcelona": "barcelone"` → `"barcelone": "barcelona"`
(French spelling keeps finding the renamed station; update the evidence
comment's match-count note). Renames feed search normally — no other search
changes.

**Hendaye country check:** `x:sncf:StopArea:OCE87677005` is currently tagged
ES but Hendaye is a French town. Verify against the geo assignment; if
confirmed wrong, fix via `station_countries.toml` override with evidence
comment (Konstanz precedent: key by current canonical id).

### 4. Cross-feed effects

`AVE INT` trains toward France may exist in BOTH renfe and sncf (ICE-82-class
duplication) and/or as border-split halves. Policy: renfe-touching
through-joins are inspected, not forbidden — legitimate border joins are what
`pipeline/through.py` exists for. Checks: (a) the 201 existing non-renfe joins
are unchanged; (b) every renfe-touching join is listed and eyeballed;
(c) duplicate full-length trains found in both feeds are documented in the
backlog's known-issues note (double-counting `direct_per_day` is a
pre-existing deferred issue, not this cycle's to fix).

### 5. Competitor feed check (bounded)

One research step: do Ouigo España or iryo publish machine-readable public
timetables (GTFS)? Outcome documented in a feeds.toml comment near the renfe
entry and in backlog item A, with the check date (evidence-comment style).
No scraping, no proprietary APIs, no further chasing this cycle.

### 6. New-feed recipe (`docs/superpowers/new-feed-recipe.md`, new)

Distills the repeatable checklist for batches 2+: research sources → verify
the REAL zip (routes/products, stop-id scheme, calendar span, agency table,
foreign stops) → feeds.toml entry with evidence comments (position chosen by
name-ownership reasoning) → fetch+build → work validation-flagged aliases →
country/name overrides → cross-feed join inspection → acceptance checks →
compute + sample refresh. Includes the research verdict table from this cycle
so batch 2 (Poland + Denmark suggested) starts warm.

## Acceptance checks (data/API level — user does visual checks themselves)

1. Build validation clean; through-join diff per §4.
2. Madrid-Puerta de Atocha and Madrid-Chamartín exist with reach files;
   search "madrid" returns them.
3. Search "barcelona" returns the single merged Barcelona-Sants (renamed), no
   duplicate station <500 m; "barcelone" still finds it via EXONYMS.
4. Madrid→Barcelona: direct connections present with plausible high frequency
   (tens per day across AVE + AVLO; iryo/Ouigo España absent by design).
5. Barcelona→Paris still reachable (existing SNCF corridor unbroken).
6. Porto Campanha exists, country PT, reachable from Vigo (TRENCELTA).
7. Hendaye country verified (and fixed if wrong).
8. Station/trip/join counts before/after diffed and explained in the report.
9. Full pytest + web tests + ruff green; `ose compute` re-run; stale reach
   files pruned (automatic).

## Out of scope this cycle

Portugal/Italy/Czechia/Hungary feeds (see verdicts), Ouigo España/iryo
ingestion (check only), country greying (item E, next), multi-day sampling
(item B), fixing cross-feed duplicate double-counting (pre-existing deferred
issue).
