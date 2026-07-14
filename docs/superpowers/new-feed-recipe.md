# New feed recipe — repeatable checklist for adding a national GTFS feed

Distilled from the Renfe integration (2026-07-10, backlog A feed 1 of N).
Each step has a STOP condition — if it triggers, report and wait for human
review before continuing.

## Pre-work: research & verify the source

- [ ] **Identify the feed URL.** HEAD-verify it is live and registration-free
      (or note the registration requirement). Record: URL, file size, license.
- [ ] **Inspect the real zip.** Document (with 2026-XX-XX date):
  - Agency table (how many operators? single or multi?)
  - Route products by `route_short_name` (full row-count table)
  - Stop-id scheme: UIC codes (7-digit) or internal? → decides `uic_regex`
  - `parent_station` hierarchy present?
  - Calendar span (must cover the sample date)
  - Foreign stops carried (which countries, how many?)
  - Name quality (diacritics? all-caps? abbreviations?)

## Step 1: `feeds.toml` entry

- [ ] Choose position by **name-ownership reasoning**: the feed must NOT register
      first for foreign stops it carries (those canonicals belong to the home feed).
      Place it AFTER all feeds whose stations it might duplicate.
- [ ] Write the `[feeds.<name>]` entry with:
  - `url`, `country`, `license` (with attribution note)
  - `route_allow` patterns (anchored `^...$` for exact product names, or `\b` for
    word boundaries — verify against `pipeline/gtfs.py` line 140: patterns are
    matched via `re.search` against both `route_short_name` and `route_long_name`)
  - `uic_regex` if stop ids contain UIC codes; omit if internal ids
  - Evidence comments: product table, calendar span, stop-id scheme, excluded products
- [ ] If the feed uses `stop_id_brand` or `trip_allow`, add those too (see SNCF/OEBB
      entries for precedent).

## Step 2: fetch + build (iterative)

- [ ] Download ONLY the new feed's zip to `data/raw/<feedname>.zip` (targeted
      curl). Never `uv run ose fetch` mid-feature — it re-downloads ALL feeds
      and silently moves the baseline data under you.
- [ ] `uv run ose build` — **STOP on SystemExit(1)**.
  - `VALIDATION: unmerged duplicate` → add alias to `station_aliases.toml` with
    evidence comment, re-run.
  - `OVERRIDE STALE` → a `station_countries.toml` or `station_names.toml` key is
    stale; fix or remove it.
  - Repeat until clean.

## Step 3: aliases + overrides

- [ ] For each cross-feed station that doesn't normalize-name-match, add an alias
      in `station_aliases.toml` (format: `"<feed>:<stop_id>" = "<canonical_id>"`).
- [ ] For stations with wrong display names (all-caps, wrong language), add entries
      in `pipeline/station_names.toml`.
- [ ] For border stations with wrong country (50m polygon imprecision), add entries
      in `pipeline/station_countries.toml`.
- [ ] All entries need evidence comments with dates and real station names.

## Step 4: cross-feed join inspection

- [ ] Verify the existing through-join count is unchanged.
- [ ] List all new-feed-touching through-joins; eyeball for legitimacy.
- [ ] Document any duplicate full-length trains found in both feeds (deferred issue,
      not this cycle's to fix).

## Step 5: acceptance checks

- [ ] Key stations exist with reach files.
- [ ] Search returns expected results.
- [ ] Direct connections present with plausible frequency.
- [ ] Station/trip/join counts before/after diffed and explained.
- [ ] Full pytest + web tests + ruff green.

## Step 6: compute + sample refresh

- [ ] `uv run ose compute` — parallel, background.
- [ ] Stale reach files pruned (automatic).
- [ ] Verify reach files for key stations.

## Step 7: EXONYMS + search (if needed)

- [ ] If the new feed renames stations that have EXONYMS entries, flip directions
      as needed (see the Barcelona `"barcelone" → "barcelona"` flip for precedent).
- [ ] Add new exonym entries for major cities if applicable.

## Research verdict table (from Renfe cycle, 2026-07-10)

| Country | Feed | Difficulty | Notes |
|---------|------|------------|-------|
| Poland | mkuran.pl community GTFS | DONE | CC BY 4.0, internal PLK stop ids |
| Denmark | Rejseplanen official GTFS | MEDIUM | direct URL open (HEAD 200, 57.5 MB, 2026-07-11); big all-modes zip needs aggressive filtering |
| Portugal | CP | HARD | Rolling 7-10-day calendar |
| Italy | Trenitalia NAP NeTEx L1 | DONE (caveated) | Direct validated gz:xml, registration-free; “No licence – No contract”, attribution required; Italo absent |
| Czechia | Ministry of Transport / CIS JŘ CZPTT NeTEx | UNFIT (verified 2026-07-14) | Official, registration-free and commercially reusable, but the national-rail archive has no coordinates or station hierarchy and no usable passenger-product labels. Do not ingest until an official coordinate source and a documented product-code mapping are available. |
| Hungary | MÁV | MEDIUM-HARD | GTFS behind corporate registration |
