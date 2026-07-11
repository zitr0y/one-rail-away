# Poland GTFS Integration Tasks

- `[x]` **Step 1: Update `feeds.toml`**
  - `[x]` Add `[feeds.pkp]` entry for `polish_trains.zip`
- `[x]` **Step 2: Build and resolve errors**
  - `[x]` Iteratively run `uv run ose build`
  - `[x]` Add aliases to `station_aliases.toml` for unmerged duplicates
  - `[x]` Add overrides to `station_names.toml` / `station_countries.toml` for stale or incorrect entries
- `[x]` **Step 3: Verify Integration**
  - `[x]` Check counts diff before and after
  - `[x]` Run full test suite `uv run pytest`
  - `[x]` Check formatting `uv run ruff check` & `uv run ruff format`
- `[x]` **Step 4: Compute Reachability**
  - `[x]` Run `uv run ose compute`
  - `[x]` Ensure key Polish connections are visible (Warszawa, Kraków)
- `[x]` **Step 5: Wrap up**
  - `[x]` Document summary in `walkthrough.md`
