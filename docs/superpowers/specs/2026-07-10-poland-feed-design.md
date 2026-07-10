# Integrate Poland GTFS (and Denmark status)

## Goal
Integrate the Polish national GTFS feed into the One Rail Away dataset to map long-distance connections across Poland. Address the Denmark feed addition request.

## Open Questions

> [!WARNING]
> **Denmark (Rejseplanen) Feed Access**
> Rejseplanen Labs no longer provides an openly accessible, registration-free URL for their static GTFS feed. It is gated behind a registration process for developers on their Labs portal. Since our principle is to use registration-free open datasets wherever possible, how would you like to proceed?
> - Option A: We skip Denmark for now and stick to Poland.
> - Option B: If you have an authorized download link or want me to use a specific mirror, please provide it.
> 
> *The plan below currently outlines the integration of Poland only.*

## Proposed Changes

### Poland GTFS (`polish_trains.zip`)

**Feed Characteristics (mkuran.pl aggregator):**
- URL: `https://mkuran.pl/gtfs/polish_trains.zip` (Replaced `pkpic.zip` recently).
- Stop IDs: 5-digit PLK internal IDs (not UIC codes). We will rely on our proximity + name matcher for border merges.
- Products: PKP Intercity (EIP, EIC, IC, TLK), international (EC, EN), and open-access operators (LEO, RJ).

#### [MODIFY] feeds.toml
We will add `[feeds.pkp]` at the end of `feeds.toml` (following our name-ownership priority rule to prevent it from minting foreign border stations first).
- `url`: "https://mkuran.pl/gtfs/polish_trains.zip"
- `route_allow`: `["^EIP$", "^EIC$", "^IC$", "^TLK$", "^LEO$", "^RJ$", "^EC$", "^EN$"]`
- We will omit `uic_regex` since the feed uses internal stop IDs.

#### [NEW] Pipeline Rebuild and Overrides
I will iteratively run `uv run ose build` to detect duplicate validation errors (due to mismatched names for border stations) and resolve them by adding the missing aliases to `station_aliases.toml`. I will also fix any incorrect display names or 50m-boundary country misses in `station_names.toml` and `station_countries.toml`.

#### [MODIFY] server/app.py (If necessary)
If any major Polish cities (like Warsaw, Krakow) have existing exonym rules that flip incorrectly when ingested from the native feed, I will adjust them. 

## Verification Plan

### Automated Tests
- Run `uv run pytest` to ensure pipeline tests and regression guards pass.
- Run `uv run ruff check` and `uv run ruff format`.

### Manual Verification
- Run `uv run ose compute` to rebuild the reachability graph.
- Diff the counts to verify that stations, trips, and connections have significantly increased.
- Manually check the graph for connections to key Polish cities like Warszawa Centralna and Kraków Główny to ensure they are properly reached from Germany (e.g. via Berlin) and Czechia (e.g. via Ostrava / Praha).
