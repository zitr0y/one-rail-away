# Country greying — design (backlog item E)

**Date:** 2026-07-11
**Status:** approved by user (treatment, data flow, binary-state decision, and all
three design sections confirmed in brainstorm)
**Backlog:** item E in `docs/superpowers/feedback-backlog.md` — make it visually
clear which countries are not yet covered, WITHOUT implying unreachability.

## Decisions (user, 2026-07-11)

- **Treatment:** translucent grey veil over non-covered countries + hover tooltip
  ("<Country> — not yet in our system") + one legend line. Styling is provisional
  until branding (backlog D) lands.
- **Data flow:** the pipeline emits `data/out/coverage.json`; web fetches it via
  the server. Adding a feed auto-un-greys its country on the next pipeline run —
  zero web changes (the A interaction the backlog asks for).
- **Binary state:** covered = a feed in `feeds.toml` declares that `country`.
  No "partial" state for leak-served countries (Belgium, Czechia, Italy…) —
  their colored reachability dots render ON TOP of the veil, which itself
  demonstrates greyed ≠ unreachable. YAGNI.

## Design

### 1. Pipeline: `data/out/coverage.json`

- Source polygons: `pipeline/assets/countries_europe_50m.geojson` (42 features,
  content-verified Natural Earth 50m subset already used for country assignment).
- Covered set: `{cfg.country for cfg in feeds.toml}` — read from `feeds.toml` at
  pipeline time, NOT from `fetch_meta.json` (known to under-report curl'd feeds;
  see backlog note). Today that is {DE, FR, AT, CH, NL, ES, PL}.
- Output: GeoJSON FeatureCollection; each feature keeps its geometry and ISO
  code, plus `covered: true|false` and a display name. (Plan correction
  2026-07-11: the asset carries ONLY `ISO_A2_EH` — no name property — so names
  come from a tested `COUNTRY_NAMES` ISO2→name table in `pipeline/coverage.py`.)
- Which stage writes it: whichever stage owns `data/out` outputs by existing
  convention (compute's output pass, like `meta.json`) — the plan pins this
  after reading the code. It must survive the stale-reach-file pruning untouched.
- TDD with fixture feeds: fixture countries flagged covered, all others not,
  feature count preserved, name property present.

### 2. Server: `GET /api/coverage`

Serves `data/out/coverage.json` like the other data/out artifacts. (Plan
corrections 2026-07-11: path is `/api/coverage` — all endpoints live under
`/api/*` and the vite proxy forwards only `/api`; 404-on-missing follows the
`reach` endpoint precedent — the server has no FileResponse pattern and
`stations.json` uses 503 via `_read`.) Nothing else.

### 3. Web: veil layer, tooltip, legend

- One fetch on load; one geojson source; one `fill` layer inserted BELOW all
  existing station/line layers, filter `covered == false`.
- Provisional paint: grey, fill-opacity ≈ 0.25 (revisit at branding).
- Hover tooltip: "<Name> — not yet in our system". The veil has NO click
  handler, and the tooltip shows only when no station/dot feature is under the
  cursor — the single-click selection precedence in `web/src/lib/pickfeature.ts`
  is untouched (regression risk called out for review).
- Legend line, exact copy: "Grey countries: not yet in our system". (Plan
  correction 2026-07-11: lives in the always-rendered `Legend.tsx`, not the
  status bar — the status bar only renders once an origin is selected, while
  the veil is always visible.)
- Pure logic (veil filter expression, tooltip-text builder, hover-precedence
  predicate) lives in a new `web/src/lib/coverage.ts` with unit tests; Map.tsx
  wiring follows the existing source/layer/effect patterns.

## Acceptance checks (data/API level — user does visual checks)

1. `coverage.json` exists after a pipeline run: 42 features, `covered` true for
   exactly the feeds.toml countries (post-ES/PL merge: DE, FR, AT, CH, NL, ES,
   PL), false otherwise, name property present on every feature.
2. `GET /coverage` returns 200 + valid GeoJSON; 404 when the file is absent.
3. Web unit tests green for coverage.ts helpers; full pytest + web tests + ruff
   green.
4. No new click handlers on the veil layer (code-level check) — selection
   behavior unchanged.

## Out of scope

Partial-coverage states, veil styling polish (branding D), any change to how
countries are assigned to stations (done, geo.py), Denmark or other new feeds
(backlog A batch 3).
