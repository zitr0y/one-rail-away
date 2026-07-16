# Intra-city transfer edges (backlog item U) — design

Approved by user 2026-07-16 (design round in-session; decisions quoted below).
Research inputs: `docs/superpowers/research/2026-07-16-intra-city-transfer-candidates.md`
plus two agent sweeps (proximity/connectivity sweep of the built dataset; web
research on transfer modes/times) merged and adversarially verified 2026-07-16.

## Problem

Multi-terminal cities have zero through trains between their terminals (Paris:
six terminals, 0 direct between any pair), so the router can never route
*through* them — a Marseille→Lille trip via Paris does not exist in the data.
City unions (item C3) fixed origin/destination display but not routing.

## Decisions (user-approved)

1. **Semantics: free footpath.** A transfer never counts toward the
   trains=1|2|3 selector; its cost is minutes added to journey duration.
   Matches RAPTOR's native footpath model.
2. **Edge source: curated pairs with minutes.** Explicit per-pair config; no
   distance-based auto-generation.
3. **Scope: all verified pairs** (critical + worthwhile tiers, plus
   web-verified pairs in covered cities: Budapest, Montpellier, Lille,
   València, and the TGV-orphan towns), creating the
   few missing small `[cities]` groups they need, plus dormant entries for
   Milano/Lisboa/Porto that activate when their feeds enter a build. The 9
   grouping-only cities from the sweep stay in backlog item Z.
4. **UI: explicit transfer leg** in journey details (mode + minutes). No map
   geometry change now (dashed connector deferred to item I rework).

## 1. Config — `[transfers]` table in `cities.toml`

Per city (same display-name key as `[cities]`), a list of
`[station A, station B, mode, minutes]` entries:

- Station references are **exact canonical station names** (same convention and
  resolution machinery as `[cities]`; churn-safe re item AM — never feed ids).
- Edges are **bidirectional**, listed once.
- `minutes` includes a safe buffer (research figures: travel + buffer).
- Modes: `walk | metro | tram | cercanias | rer | train-shuttle | bus`
  (display hint only; router treats all identically).
- Unresolved names **warn and skip**, never fail the build — same policy as
  `[cities]` members. This is what lets Milano/Lisboa/Porto entries sit
  dormant until their feeds are in a build.
- A transfer pair whose stations do not share a `[cities]` group is a build
  warning (skip the edge): groups are the umbrella; edges only exist inside one.

The exact block (station names validated against `data/out/stations.json`) is
appended in the Appendix and is the source of truth for the initial curation.

## 2. Router — footpaths between rounds only

- `pipeline/cities.py` resolves `[transfers]` → list of
  `(station_id_a, station_id_b, seconds, mode)` at compute time, after station
  merge (so ids are the merged canonical ones).
- RAPTOR consumes them as standard footpaths applied **between rounds only** —
  a transfer must be preceded AND followed by a train leg. Never the first or
  last leg of a journey. Rationale: trains=1 keeps meaning "genuinely direct";
  city-union origins already union member reach, so nothing is lost at the
  origin side.
- One transfer per round boundary (standard RAPTOR footpath relaxation — no
  footpath chaining within a round).

## 3. Reach schema + web UI

- Journeys gain a transfer leg between train legs:
  `{type: "transfer", mode, minutes, from_id, to_id}` (train legs unchanged).
- Web journey details render it as an explicit line: walk icon "~15 min walk
  to Gare de Lyon" / metro icon "~45 min metro to Montparnasse". Copy uses "~"
  — these are estimates with buffer, not promises (item B language rule).
- `direct_per_day`, frequency counts, and all "per day" figures stay
  **trains-only** — a footpath is not a departure.
- Reach-file size impact expected negligible (one extra leg object on the
  minority of journeys that cross a city).

## 4. Testing

- Synthetic fixture feed only (item AD rule: no live feed ids): two terminal
  stations + a third city, one `[transfers]` entry.
- Assert: RAPTOR routes A→terminal1→(footpath)→terminal2→C as 2 trains;
  journey carries the transfer leg; the same journey is absent when the
  transfer is removed.
- Assert: a footpath is never first or last leg (destination reached only via
  final footpath does NOT count as reached).
- Assert: unresolved station name in `[transfers]` → warning logged, edge
  skipped, build succeeds.
- Assert: pair not sharing a `[cities]` group → warning, edge skipped.

## 5. Out of scope

- The 9 grouping-only cities from the sweep (backlog item Z).
- Medina del Campo AV coordinate bug (~3.3 km off; goes to backlog notes).
- Map connector / rider handling of transfers (item I geometry rework).
- Frequency histograms (item AO), departure-time filter (item AQ).
- Any change to how city unions themselves work.

## Appendix — initial curated block

Validated against `data/out/stations.json` (build of 2026-07-13; note this
build predates the CP + Trenitalia feeds, hence the dormant entries).

All station names below validated against the build's `stations.json` except
the dormant Lisboa/Porto names (feeds absent; expected to warn-and-skip until
curated when CP lands). The existing `"Madrid"` group gains the
`"Madrid-Atocha Cercanías"` member; all other `[cities]` lines are new groups.
Milano Porta Garibaldi's canonical name is all-caps in the current feed data —
use it verbatim (renaming is item-Z-adjacent cleanup, not this change).

```toml
# --- additions to [cities] ---
"Madrid" = ["Madrid-Puerta de Atocha-Almudena Grandes", "Madrid-Chamartín-Clara Campoamor", "Madrid-Atocha Cercanías"]
"Budapest" = ["Budapest-Keleti", "Budapest-Nyugati"]
"Montpellier" = ["Montpellier Saint-Roch", "Montpellier Sud de France"]
"Lille" = ["Lille Europe", "Lille Flandres"]
"València" = ["València-Estació del Nord", "València-Joaquín Sorolla"]
"Valence" = ["Valence Ville", "Valence TGV Rhône-Alpes Sud"]
"Reims" = ["Reims", "Champagne-Ardenne TGV"]
"Mâcon" = ["Mâcon", "Mâcon - Loché TGV"]
"Lyon" = ["Lyon Part Dieu", "Lyon Perrache", "Lyon Saint-Exupéry TGV"]
"Milano" = ["Milano Centrale", "MILANO PORTA GARIBALDI"]
"Lisboa" = ["Lisboa Santa Apolónia", "Lisboa Oriente"]          # dormant: awaiting CP feed
"Porto" = ["Porto Campanhã", "Porto São Bento"]                 # dormant: awaiting CP feed

# --- new [transfers] table ---
[transfers]
"Paris" = [
  ["Paris Gare de Lyon Hall 1 - 2", "Paris Est", "metro", 45],
  ["Paris Gare de Lyon Hall 1 - 2", "Paris Gare du Nord", "rer", 40],
  ["Paris Gare de Lyon Hall 1 - 2", "Paris Austerlitz", "walk", 15],
  ["Paris Gare de Lyon Hall 1 - 2", "Paris Montparnasse Hall 1 - 2", "metro", 45],
  ["Paris Gare de Lyon Hall 1 - 2", "Paris Bercy Bourg. Pays d'Auv.", "walk", 20],
  ["Paris Est", "Paris Gare du Nord", "walk", 15],
  ["Paris Est", "Paris Austerlitz", "metro", 35],
  ["Paris Est", "Paris Montparnasse Hall 1 - 2", "metro", 55],
  ["Paris Est", "Paris Bercy Bourg. Pays d'Auv.", "metro", 50],
  ["Paris Gare du Nord", "Paris Austerlitz", "metro", 35],
  ["Paris Gare du Nord", "Paris Montparnasse Hall 1 - 2", "metro", 55],
  ["Paris Gare du Nord", "Paris Bercy Bourg. Pays d'Auv.", "metro", 50],
  ["Paris Austerlitz", "Paris Montparnasse Hall 1 - 2", "metro", 45],
  ["Paris Austerlitz", "Paris Bercy Bourg. Pays d'Auv.", "walk", 25],
  ["Paris Montparnasse Hall 1 - 2", "Paris Bercy Bourg. Pays d'Auv.", "metro", 45],
]
"Köln" = [
  ["Köln Hbf", "Köln Messe/Deutz", "walk", 15],
]
"Amsterdam" = [
  ["Amsterdam Centraal", "Amsterdam Zuid", "metro", 25],
  ["Amsterdam Sloterdijk", "Amsterdam Zuid", "metro", 25],
  ["Amsterdam Zuid", "Amsterdam Amstel", "metro", 25],
]
"Madrid" = [
  ["Madrid-Puerta de Atocha-Almudena Grandes", "Madrid-Atocha Cercanías", "walk", 15],
]
"Berlin" = [
  ["Berlin Ostkreuz", "Berlin Hbf", "rer", 30],
]
"Frankfurt" = [
  ["Frankfurt(Main)Süd", "Frankfurt(Main)West", "rer", 30],
  ["Frankfurt(Main)Süd", "Frankfurt(Main)Hbf", "metro", 25],
]
"Budapest" = [
  ["Budapest-Keleti", "Budapest-Nyugati", "metro", 35],
]
"Montpellier" = [
  ["Montpellier Saint-Roch", "Montpellier Sud de France", "tram", 50],
]
"Lille" = [
  ["Lille Europe", "Lille Flandres", "walk", 15],
]
"València" = [
  ["València-Estació del Nord", "València-Joaquín Sorolla", "walk", 20],
]
"Valence" = [
  ["Valence Ville", "Valence TGV Rhône-Alpes Sud", "train-shuttle", 25],
]
"Reims" = [
  ["Reims", "Champagne-Ardenne TGV", "train-shuttle", 25],
]
"Mâcon" = [
  ["Mâcon", "Mâcon - Loché TGV", "bus", 40],
]
"Lyon" = [
  ["Lyon Part Dieu", "Lyon Saint-Exupéry TGV", "tram", 50],
  ["Lyon Perrache", "Lyon Saint-Exupéry TGV", "tram", 60],
]
"Milano" = [
  ["Milano Centrale", "MILANO PORTA GARIBALDI", "metro", 25],   # dormant: awaiting Trenitalia in build
]
"Lisboa" = [
  ["Lisboa Santa Apolónia", "Lisboa Oriente", "train-shuttle", 20],   # dormant: awaiting CP feed
]
"Porto" = [
  ["Porto Campanhã", "Porto São Bento", "train-shuttle", 15],   # dormant: awaiting CP feed
]
```
