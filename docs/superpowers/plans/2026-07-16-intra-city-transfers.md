# Intra-City Transfers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add curated, bidirectional intra-city transfer footpaths that are resolved from canonical station names after station merging, are usable only between train rounds, serialize as explicit transfer legs, and render explicitly in journey details.

**Architecture:** Extend `pipeline/cities.py` with a non-fatal `[transfers]` loader that returns `(station_id_a, station_id_b, seconds, mode)` tuples from the already-merged station registry. Thread those tuples through serial and process-pool compute paths into RAPTOR. RAPTOR will create one-hop boarding readiness between train rounds, while its published arrivals remain train arrivals; parent pointers will retain any footpath used so reconstruction can interleave unchanged train legs with the new transfer-leg schema. The server remains a byte-for-byte artifact server. The web app will use a discriminated train/transfer union, omit transfer objects from rail geometry, and render transfer details explicitly.

**Tech Stack:** Python 3.14, TOML (`tomllib`), Pydantic 2, pytest, React 19, TypeScript 6, Vitest.

## Global Constraints

- The approved design at `docs/superpowers/specs/2026-07-16-intra-city-transfers-design.md` is authoritative.
- The Appendix TOML fenced block is copied into `cities.toml` verbatim; do not reword comments, normalize capitalization, reorder pairs, or alter minutes/modes.
- Tests use synthetic station ids and synthetic timetables only. Never copy an id from `data/out/stations.json` or any live feed into a test.
- A footpath is bidirectional, costs time, does not increment `Journey.trains`, and can occur only between two train legs.
- A journey may use at most one footpath at each train-round boundary; never chain footpaths without an intervening train.
- `direct_per_day`, `Frequency.direct_*`, and all per-day counts remain train-only.
- Do not change `server/app.py`: `/api/reach/{station_id}` already serves reach JSON byte-for-byte via `_artifact_response`.
- Do not add map connector geometry. Transfer legs must be type-safe in map consumers and must not be passed to `legSegments`.
- Do not push commits. Keep each task's diff within its declared expected surface.
- Baseline recorded while planning: `uv run pytest --collect-only -q` collects 247 cases; `cd web && npm test -- --reporter=dot` passes 187 cases.
- Existing Ruff violations are on lines in files this work already touches (`pipeline/compute.py` and `tests/test_cities.py`); wrap those lines while editing so the final touched-file Ruff command is clean.

---

### Task 1: Parse, validate, and resolve `[transfers]` without failing the build

**Expected diff surface:**
- Modify: `pipeline/cities.py`
- Modify: `pipeline/models.py` (shared `TransferMode` type alias only)
- Modify: `tests/test_cities.py`
- No other files.

**Public contract introduced:**

```python
# pipeline/models.py
TransferMode = Literal[
    "walk", "metro", "tram", "cercanias", "rer", "train-shuttle", "bus"
]

# pipeline/cities.py
ResolvedTransfer = tuple[str, str, int, TransferMode]


def load_transfers(
    path: Path, stations: list[Station]
) -> tuple[list[ResolvedTransfer], list[str]]:
    """Resolve valid configured pairs against an already-merged station list."""
```

The tuple order is exactly `(station_id_a, station_id_b, seconds, mode)`. The loader returns each configured edge once; RAPTOR is responsible for traversing it in both directions.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add five failing synthetic tests to `tests/test_cities.py`**

Add these exact test functions (five new pytest cases; this file goes from 3 to 8 cases at this point):

1. `test_load_transfers_resolves_names_to_post_merge_ids_and_seconds`
   - Write a temporary TOML containing synthetic `Metroville` stations `South Terminal` and `North Terminal`, plus one `metro`, 17-minute transfer.
   - Pass `Station` objects whose ids are `merged-south` and `merged-north`; these ids deliberately represent the post-merge canonical ids.
   - Assert the exact result is `[('merged-south', 'merged-north', 1020, 'metro')]` and warnings are empty.
2. `test_load_transfers_warns_and_skips_unresolved_station`
   - Put both names in `[cities]`, omit `Missing Terminal` from the synthetic station list, and assert `transfers == []`.
   - Assert one returned warning contains `Metroville`, `Missing Terminal`, and `no station matches transfer`; use `caplog` to assert it was logged at WARNING.
3. `test_load_transfers_warns_and_skips_pair_outside_declared_city_group`
   - Define both synthetic stations, but include only `South Terminal` in `[cities].Metroville` and place `North Terminal` in another group.
   - Assert the edge is skipped and one warning contains `does not share` and `Metroville`.
4. `test_load_transfers_warns_and_skips_invalid_entries`
   - In one temporary file include four invalid entries: wrong arity, unsupported mode `taxi`, zero minutes, and non-integer minutes.
   - Assert all are skipped, exactly four warnings are returned/logged, and the function returns normally.
5. `test_load_transfers_missing_file_is_empty`
   - Assert a missing path returns `([], [])`.

Use only `_station("synthetic-id", "Synthetic Name")`; do not add feed fixtures or production ids.

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run:

```bash
uv run pytest tests/test_cities.py -q
```

Expected before implementation: collection fails because `load_transfers` does not exist. Do not proceed if the failure is unrelated.

- [ ] **Step 3: Implement the shared mode type and semantic parsing/validation**

Add `TransferMode` to `pipeline/models.py` beside the existing model-level `Literal` import. In `pipeline/cities.py`, import `TransferMode`, add `cast` plus `ResolvedTransfer`, and define a constant set containing exactly the seven approved modes. Reuse the same exact-name index shape as `load_cities` (`dict[str, list[str]]`), because the `stations` argument is already the output of the station merge.

For each `[transfers].<city>` entry, validate in this order:

1. The entry is a four-item list.
2. Endpoints and mode are strings; minutes is an `int` but not a `bool`, and is greater than zero.
3. Mode is in the approved set.
4. The same `<city>` key exists in `[cities]` and both endpoint names occur in that exact group's member list.
5. Each endpoint resolves by exact canonical name to exactly one post-merge station id.

Every failed check calls one local helper that both `log.warning(msg)` and appends `msg` to the returned list, then skips only that entry. Use stable warning prefixes so tests and build output are actionable:

```python
f"cities.toml: invalid transfer entry for {city!r}: {entry!r}"
f"cities.toml: unsupported transfer mode for {city!r}: {mode!r}"
f"cities.toml: transfer {city!r} pair {a!r} -> {b!r} does not share that [cities] group"
f"cities.toml: no station matches transfer {city!r} endpoint {name!r}"
f"cities.toml: transfer {city!r} endpoint {name!r} is ambiguous after merge, skipping"
```

On success append:

```python
transfers.append((ids_a[0], ids_b[0], minutes * 60, cast(TransferMode, mode)))
```

Do not synthesize reverse tuples, auto-connect a city group, infer by distance, or raise on a semantically invalid transfer entry.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_cities.py -q
```

Expected: `8 passed`.

---

### Task 2: Add the reach-file transfer-leg model without changing train legs

**Expected diff surface:**
- Modify: `pipeline/models.py`
- Modify: `tests/test_models.py`
- No other files.

**Model contract introduced:**

```python
class TransferLeg(BaseModel):
    type: Literal["transfer"] = "transfer"
    mode: TransferMode
    minutes: int
    from_id: str
    to_id: str


JourneyLeg = Leg | TransferLeg


class Journey(BaseModel):
    trains: int
    duration_min: int
    legs: list[JourneyLeg]
```

Keep the existing `Leg` fields and serialized shape unchanged; in particular, do not add `type: "train"` to train legs.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add two failing model tests**

Add exactly:

1. `test_transfer_leg_serializes_exact_schema`
   - Construct `TransferLeg(mode="walk", minutes=15, from_id="terminal-a", to_id="terminal-b")`.
   - Assert `model_dump()` equals exactly:

```python
{
    "type": "transfer",
    "mode": "walk",
    "minutes": 15,
    "from_id": "terminal-a",
    "to_id": "terminal-b",
}
```

2. `test_reach_file_round_trip_with_train_and_transfer_legs`
   - Build a two-train `Journey` with `[Leg(...), TransferLeg(...), Leg(...)]` and synthetic ids.
   - Round-trip with `ReachFile.model_validate_json(rf.model_dump_json(by_alias=True))`.
   - Assert the middle object is a `TransferLeg`, its mode/minutes survive, and `journey.trains == 2` while `len(journey.legs) == 3`.

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_models.py -q
```

Expected before implementation: import/validation failure because `TransferLeg` does not exist.

- [ ] **Step 3: Implement the union in `pipeline/models.py`**

Reuse the `TransferMode` alias added to `pipeline.models` in Task 1, and keep `ResolvedTransfer` in `pipeline.cities`; this preserves the exact contracts above without making models depend on config loading.

Do not put train-only fields (`train`, `dep`, `arr`, `via`, `feeds`) on `TransferLeg`. Pydantic can distinguish the union because the transfer shape requires `type="transfer"` and the train shape requires `train`.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/test_models.py -q
```

Expected: `4 passed` (2 existing + 2 new).

---

### Task 3: Inject one bidirectional footpath between train rounds only

**Expected diff surface:**
- Modify: `pipeline/raptor.py`
- Modify: `tests/test_raptor.py`
- No other files.

**Function signatures after this task:**

```python
def _raptor(
    trips, origin, dep_floor, max_trains, transfer_min,
    footpaths: list[ResolvedTransfer],
): ...


def compute_reachability(
    trips: list[Trip],
    origin: str,
    max_trains: int = 3,
    transfer_min: int = 10,
    footpaths: list[ResolvedTransfer] | None = None,
) -> dict[str, list[Journey]]: ...
```

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add three failing synthetic RAPTOR tests**

Append these exact cases (this file goes from 14 to 17 cases):

1. `test_bidirectional_footpath_connects_two_train_rounds_and_emits_leg`
   - Forward timetable: `Origin -> South Terminal` arrives 600; `North Terminal -> Destination` departs 630; footpath is `("south", "north", 20 * 60, "metro")`.
   - Assert Destination is absent without `footpaths`, present with it, has `trains == 2`, `duration_min` includes the 20-minute transfer/wait interval, and leg types/order are train, transfer, train.
   - Assert the transfer object is exactly `mode="metro", minutes=20, from_id="south", to_id="north"`.
   - In the same test, use a synthetic reverse-direction pair of trips and the same one-way-listed tuple to prove traversal from `north` to `south` also works.
2. `test_footpath_is_never_first_or_last_leg`
   - First-leg case: footpath `origin -> terminal`, followed by a train `terminal -> destination`; assert destination is absent.
   - Last-leg case: train `origin -> terminal`, followed only by a footpath `terminal -> destination`; assert destination is absent even though terminal is present.
3. `test_footpaths_do_not_chain_within_one_round_boundary`
   - Train reaches A, configure A-B and B-C footpaths, and put an onward train only at C. Assert its destination is absent.
   - Also put a separate onward train at B and assert that destination is present, proving exactly one footpath relaxation occurred rather than disabling footpaths wholesale.

All ids are short synthetic strings (`origin`, `south`, `north`, `destination`); all times remain inside the existing 05:00-20:00 floor window.

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_raptor.py -q
```

Expected before implementation: the new `footpaths=` argument is rejected.

- [ ] **Step 3: Separate train arrivals from boarding readiness**

Replace the positional parent tuple with a `NamedTuple` (or frozen dataclass) carrying these exact logical fields:

```python
class Parent(NamedTuple):
    trip: Trip
    previous_station: str       # station reached by the preceding train
    board_station: str          # may differ after a footpath
    board_dep: int
    alight_arr: int
    board_idx: int
    alight_idx: int
    footpath: ResolvedTransfer | None  # directional source -> target tuple
```

For each round `k`:

1. `arr[k - 1]` remains the earliest arrivals at stations reached by a train (plus existing carry-forward entries). Never write a footpath target into `arr` by itself.
2. Initialize `ready[station]` from `prev[station] + transfer_min`, except the origin retains its existing zero buffer. Store `(previous_station=station, footpath=None)` for that readiness.
3. Only when `k > 1`, relax each configured tuple once in both directions. A source is eligible only when `(k - 1, source)` exists in `parent`, proving a train precedes it. Use `seconds // 60`; loader-produced values are exact multiples of 60.
4. Compare each one-hop candidate `prev[source] + footpath_minutes` with the existing readiness for the target. A strict improvement replaces readiness metadata with `(source, (source, target, seconds, mode))`. Do not read newly written readiness values as footpath sources.
5. Build candidate trips from `ready`, and change the boarding condition to `ready_get(station, INF) <= s_dep`; the generic same-station buffer is already represented in `ready` and must not be added twice.
6. When a train improves `cur[station]`, its `Parent.previous_station` and optional footpath come from the chosen readiness at its boarding station.

Keep `cur = dict(prev)` and the current parent carry-forward behavior. That preserves true leg counts for earlier-round winners.

- [ ] **Step 4: Reconstruct interleaved legs**

Update `_walk` to step from each train alight to `Parent.previous_station` and decrement the round once. It still increments `trains` exactly once per parent record; a footpath never increments it.

Update `_build_legs` to append, while walking backward:

```python
legs.append(Leg(
    train=p.trip.train,
    dep=fmt(p.board_dep),
    arr=fmt(p.alight_arr),
    **{"from": p.board_station},
    to=st,
    via=[x.station for x in p.trip.stops[p.board_idx + 1 : p.alight_idx]],
    feeds=p.trip.feeds,
))
if p.footpath is not None:
    from_id, to_id, seconds, mode = p.footpath
    legs.append(TransferLeg(
        mode=mode, minutes=seconds // 60, from_id=from_id, to_id=to_id,
    ))
```

Then step to `p.previous_station`, decrement the round, and reverse once at the end. Appending train then transfer during the backward walk is intentional: reversal yields `[earlier train, transfer, later train]`.

- [ ] **Step 5: Run focused regression tests**

```bash
uv run pytest tests/test_raptor.py -q
```

Expected: `17 passed`; the 14 existing no-footpath cases must remain byte-semantically unchanged.

---

### Task 4: Resolve transfers before compute and write them through serial/parallel reach files

**Expected diff surface:**
- Modify: `pipeline/compute.py`
- Modify: `tests/test_compute.py`
- No changes to `server/app.py`, `pipeline/artifacts.py`, or feed/build code.

**Function signatures after this task:**

```python
def _aggregate_reach(
    trips_by_date: dict[str, list[Trip]],
    station_id: str,
    feed_validity_by_date: dict[str, dict[str, dict[str, object]]] | None = None,
    extra_trips: list[Trip] | None = None,
    footpaths: list[ResolvedTransfer] | None = None,
) -> list[Destination]: ...


def _write_reach(
    trips_by_date: dict[str, list[Trip]],
    station_id: str,
    out_dir: Path,
    sample_date: str,
    now: str,
    feed_validity_by_date: dict[str, dict[str, dict[str, object]]] | None = None,
    extra_trips: list[Trip] | None = None,
    footpaths: list[ResolvedTransfer] | None = None,
) -> int: ...


def compute_all(
    graph_dir: Path,
    out_dir: Path,
    workers: int | None = None,
    feeds_path: Path = Path("feeds.toml"),
    cities_path: Path = Path("cities.toml"),
) -> None: ...
```

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add a reusable synthetic transfer graph helper and two failing compute tests**

In `tests/test_compute.py`, add a private helper that writes:

- `stations.json`: synthetic stations `origin`, `south`, `north`, `destination`, with names `Origin`, `South Terminal`, `North Terminal`, `Destination`.
- `trips.json`: one train `Origin -> South Terminal` and one train `North Terminal -> Destination`, on one synthetic sample date.
- `cities.toml`: a `[cities].Metroville` group and optionally its 20-minute `[transfers].Metroville` entry.

Add exactly:

1. `test_compute_all_writes_two_train_journey_with_transfer_leg`
   - Compute once with a no-transfer TOML and assert `destination` is absent from `reach_origin.json` (or no matching destination exists).
   - Compute into another output with the transfer TOML passed as `cities_path=`.
   - Assert a destination now exists with `trains == 2`, exactly three ordered legs, and middle leg exactly:

```python
{
    "type": "transfer",
    "mode": "metro",
    "minutes": 20,
    "from_id": "south",
    "to_id": "north",
}
```

   - Assert both train objects retain their old schema (`train`, `dep`, `arr`, `from`, `to`, `via`; no `type`).
   - Assert `direct_per_day == 0`, `frequency["direct_trips"] == 0`, and journey duration includes the footpath time.
2. `test_compute_all_transfer_route_matches_in_parallel`
   - Run that same tiny graph with `workers=1` and `workers=2`.
   - Remove only `computed_at` before comparison and assert all `reach_*.json` payloads are identical, including the transfer leg.

This adds two cases; `tests/test_compute.py` goes from 15 to 17 cases.

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_compute.py -q
```

Expected before implementation: `compute_all(..., cities_path=...)` is rejected and no cross-terminal journey is written.

- [ ] **Step 3: Resolve config immediately after loading merged graph stations**

In `compute_all`, immediately after constructing `stations = [Station(**s) ...]`, call both:

```python
city_groups, city_warnings = load_cities(cities_path, stations)
footpaths, transfer_warnings = load_transfers(cities_path, stations)
for warning in [*city_warnings, *transfer_warnings]:
    print(warning)
```

This location is the post-merge boundary: `graph/stations.json` and every trip stop already use canonical merged ids. Remove the later duplicate `load_cities(Path("cities.toml"), stations)` call, but keep writing the already-resolved `city_groups` to `cities.json`.

- [ ] **Step 4: Thread the same footpaths through every compute path**

- Pass `footpaths=footpaths` to every per-date and `extra_trips` call to `compute_reachability` in `_aggregate_reach`.
- Pass it from `_write_reach` into `_aggregate_reach`.
- Add `_worker_footpaths: list[ResolvedTransfer] = []`.
- Change `_worker_init` to `def _worker_init(graph_dir_str: str, footpaths: list[ResolvedTransfer]) -> None`, load graph data as before, then assign `_worker_footpaths = footpaths`.
- Initialize the pool with `initargs=(str(graph_dir), footpaths)` and pass `_worker_footpaths` from `_compute_one` into `_write_reach`.
- Pass the parent-resolved list directly in the serial branch. Do not reload TOML inside each worker or once per origin.

In `_aggregate_reach`, make feed provenance explicitly train-only now that `Journey.legs` is a union:

```python
frozenset(
    feed
    for leg in journey.legs
    if isinstance(leg, Leg)
    for feed in leg.feeds
)
```

Leave `_direct_counts` unchanged; it scans actual trips and therefore already excludes transfers.

- [ ] **Step 5: Verify writer, process pool, warnings, and server pass-through**

```bash
uv run pytest tests/test_compute.py tests/test_server.py -q
```

Expected: `50 passed` (17 compute + the existing 33 server cases). `server/app.py` must remain absent from `git diff --name-only`.

---

### Task 5: Make web journey consumers type-safe while keeping transfers out of rail geometry

**Expected diff surface:**
- Modify: `web/src/lib/types.ts`
- Modify: `web/src/lib/geojson.ts`
- Modify: `web/src/lib/geojson.test.ts`
- Modify: `web/src/components/Map.tsx`
- No CSS or journey-details rendering yet.

**Type contract introduced:**

```typescript
export type TransferMode =
  | "walk" | "metro" | "tram" | "cercanias" | "rer" | "train-shuttle" | "bus";

export interface Leg {
  type?: never;
  train: string; dep: string; arr: string; from: string; to: string; via: string[];
}

export interface TransferLeg {
  type: "transfer";
  mode: TransferMode;
  minutes: number;
  from_id: string;
  to_id: string;
}

export type JourneyLeg = Leg | TransferLeg;
export interface Journey { trains: number; duration_min: number; legs: JourneyLeg[] }
```

Keep `Leg` as the exported train-leg name so existing geometry fixtures and helpers remain clear.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add one failing geometry-compatibility test**

In `web/src/lib/geojson.test.ts`, add:

`it("keeps transfer legs out of rail-path geometry", () => { ... })`

Build a synthetic journey with train `a -> b`, transfer `b -> c`, and train `c -> d`. Assert `journeyLegPaths` returns exactly two paths (the two train legs), and no returned path is generated from the transfer object itself. Use synthetic stations only.

- [ ] **Step 2: Run and confirm failure**

```bash
cd web
npx vitest run src/lib/geojson.test.ts
```

Expected before implementation: TypeScript rejects the transfer shape or geometry treats it as a train leg.

- [ ] **Step 3: Add the union and narrow every train-only consumer**

In `web/src/lib/types.ts`, add the types above.

In `web/src/lib/geojson.ts`, add one shared type guard:

```typescript
export function isTrainLeg(leg: JourneyLeg): leg is Leg {
  return leg.type !== "transfer";
}
```

Use it before every call to `legSegments` and in `journeyLegPaths`/`segmentsGeoJSON`; never reinterpret `from_id`/`to_id` as a rail hop. Update `transferPoints` to derive its existing train-change points from the filtered train-leg sequence, so through stops remain excluded and old two-/three-train tests retain their meaning.

In `web/src/components/Map.tsx::syncHighlight`, branch on the discriminant:

```typescript
if (leg.type === "transfer") {
  ids.add(leg.from_id);
  ids.add(leg.to_id);
} else {
  ids.add(leg.from);
  ids.add(leg.to);
  for (const via of leg.via) ids.add(via);
}
```

This keeps both terminals highlighted without adding a connector layer.

- [ ] **Step 4: Verify focused web tests and typecheck**

```bash
cd web
npx vitest run src/lib/geojson.test.ts
npm run build
```

Expected: `37 passed` in `geojson.test.ts` (36 existing + 1 new), and the production TypeScript/Vite build succeeds.

---

### Task 6: Render an explicit transfer line with mode icon and approximate wording

**Expected diff surface:**
- Modify: `web/src/components/TripDetails.tsx`
- Modify: `web/src/components/TripDetails.test.tsx`
- Modify: `web/src/index.css`
- No pipeline or map files.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add two failing TripDetails tests**

Add exactly:

1. `it("renders an explicit transfer line with icon and approximate minutes", ...)`
   - Extend a local synthetic `stationsById` with `South Terminal` and `North Terminal`.
   - Render train, `{type: "transfer", mode: "metro", minutes: 20, from_id: "south", to_id: "north"}`, train.
   - Assert the markup contains `~20 min metro to North Terminal`, contains the metro icon with `aria-hidden="true"`, and still contains both train names.
   - Assert the transfer row has class `transfer-leg` and does not render `undefined`.
2. `it("provides an icon for every configured transfer mode", ...)`
   - Call the exported `transferModeIcon` once for each of the seven `TransferMode` values in a plain loop.
   - Assert every result is a non-empty string. Do not use `it.each`; this remains one Vitest case so counts stay exact.

- [ ] **Step 2: Run and confirm failure**

```bash
cd web
npx vitest run src/components/TripDetails.test.tsx
```

Expected before implementation: `TripDetails` accesses train-only fields and no transfer wording/icon exists.

- [ ] **Step 3: Implement accessible transfer rendering**

Export this complete icon mapping from `TripDetails.tsx`:

```typescript
const TRANSFER_MODE_ICONS: Record<TransferMode, string> = {
  walk: "🚶",
  metro: "🚇",
  tram: "🚋",
  cercanias: "🚆",
  rer: "🚆",
  "train-shuttle": "🚆",
  bus: "🚌",
};

export function transferModeIcon(mode: TransferMode): string {
  return TRANSFER_MODE_ICONS[mode];
}
```

Replace the unconditional train `<li>` in the `journey.legs.map` with a discriminated branch. The transfer branch must use this exact visible text order:

```tsx
<li className="transfer-leg" key={`transfer-${leg.from_id}-${leg.to_id}`}>
  <span className="transfer-icon" aria-hidden="true">{transferModeIcon(leg.mode)}</span>
  {" "}~{leg.minutes} min {leg.mode} to{" "}
  {stationsById.get(leg.to_id)?.name ?? leg.to_id}
</li>
```

Keep the existing train row wording unchanged. In `web/src/index.css`, add only small presentation rules under `.trip-details .legs`, for example a muted color for `.transfer-leg` and fixed inline width/alignment for `.transfer-icon`; do not add a map connector style.

- [ ] **Step 4: Verify details rendering**

```bash
cd web
npx vitest run src/components/TripDetails.test.tsx
```

Expected: `7 passed` (5 existing + 2 new).

---

### Task 7: Apply the approved Appendix config to `cities.toml` verbatim

**Expected diff surface:**
- Modify: `cities.toml`
- Modify: `tests/test_cities.py`
- No other files.

**Implementation guard:** if a test fails, do NOT hack the implementation or invent special cases — use the plan code verbatim, else STOP and report the contradiction.

- [ ] **Step 1: Add a failing verbatim-config regression test**

Add `test_shipped_transfer_config_matches_approved_appendix_verbatim` to `tests/test_cities.py`. It must read the authoritative spec, extract the single fenced TOML block, and assert that exact string occurs contiguously in `cities.toml`:

```python
repo = Path(__file__).parent.parent
spec = repo.joinpath(
    "docs/superpowers/specs/2026-07-16-intra-city-transfers-design.md"
).read_text(encoding="utf-8")
approved = spec.split("```toml\n", 1)[1].split("\n```", 1)[0]
shipped = repo.joinpath("cities.toml").read_text(encoding="utf-8")
assert approved in shipped
```

This is a text/config regression test, not a feed fixture; it contains no live station ids.

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/test_cities.py::test_shipped_transfer_config_matches_approved_appendix_verbatim -q
```

Expected before config edit: one assertion failure because the block is not yet shipped.

- [ ] **Step 3: Copy the Appendix block exactly**

In `cities.toml`:

1. Remove the existing two-member `"Madrid"` line from its old location so TOML does not contain a duplicate key.
2. Immediately after the current `"Roma"` entry (while still inside `[cities]`), paste the authoritative spec's entire fenced TOML block, starting at `# --- additions to [cities] ---` and ending at the closing Porto transfer entry.
3. Do not edit any pasted character. This intentionally moves the Madrid declaration into the approved block and upgrades it to three members.

Do not hand-copy from this plan; copy directly from `docs/superpowers/specs/2026-07-16-intra-city-transfers-design.md` so the test enforces the user-approved source.

- [ ] **Step 4: Verify exact text and TOML parsing**

```bash
uv run pytest tests/test_cities.py -q
uv run python -c 'import tomllib; tomllib.load(open("cities.toml", "rb"))'
```

Expected: `9 passed` in `tests/test_cities.py` and the parser command exits 0.

---

### Task 8: Final synthetic Marseille-to-Lille-style verification and full suite

**Expected diff surface:**
- None. This is verification only; do not edit files to make commands pass.

- [ ] **Step 1: Re-run the small end-to-end recompute proof**

```bash
uv run pytest \
  tests/test_compute.py::test_compute_all_writes_two_train_journey_with_transfer_leg \
  tests/test_compute.py::test_compute_all_transfer_route_matches_in_parallel \
  -q
```

Expected: `2 passed`. The first test is the synthetic equivalent of Marseille -> Paris Gare de Lyon -> intra-Paris transfer -> Paris Gare du Nord -> Lille: absent without the edge, present with exactly 2 trains + 1 transfer leg.

- [ ] **Step 2: Run focused backend feature tests**

```bash
uv run pytest tests/test_cities.py tests/test_models.py tests/test_raptor.py tests/test_compute.py -q
```

Expected: `47 passed` (9 + 4 + 17 + 17).

- [ ] **Step 3: Run all Python tests and touched-file lint**

```bash
uv run pytest -q
uv run ruff check \
  pipeline/cities.py pipeline/models.py pipeline/raptor.py pipeline/compute.py \
  tests/test_cities.py tests/test_models.py tests/test_raptor.py tests/test_compute.py
```

Expected: `260 passed` (baseline 247 + 13 new), then Ruff exits clean.

- [ ] **Step 4: Run all web tests, lint, and production build**

```bash
cd web
npm test -- --reporter=dot
npm run lint
npm run build
```

Expected: `190 passed` across 23 files (baseline 187 + 3 new), lint exits clean, and TypeScript/Vite build succeeds.

- [ ] **Step 5: Audit scope and schema**

```bash
git diff --name-only
git diff --check
```

Expected changed implementation/test files only:

```text
cities.toml
pipeline/cities.py
pipeline/compute.py
pipeline/models.py
pipeline/raptor.py
tests/test_cities.py
tests/test_compute.py
tests/test_models.py
tests/test_raptor.py
web/src/components/Map.tsx
web/src/components/TripDetails.test.tsx
web/src/components/TripDetails.tsx
web/src/index.css
web/src/lib/geojson.test.ts
web/src/lib/geojson.ts
web/src/lib/types.ts
```

Also expect this plan file if implementation occurs in the same worktree. Confirm `server/app.py`, `pipeline/build.py`, `pipeline/merge.py`, rail-path artifacts, and generated `data/out/*` are untouched. Inspect one synthetic reach JSON and confirm its train legs have no `type`, its transfer leg has exactly the five approved keys, and train/frequency counts exclude the transfer.

## Expected Test Delta

- Python: +13 cases, 247 -> 260.
  - `tests/test_cities.py`: +6 (3 -> 9).
  - `tests/test_models.py`: +2 (2 -> 4).
  - `tests/test_raptor.py`: +3 (14 -> 17).
  - `tests/test_compute.py`: +2 (15 -> 17).
- Web: +3 cases, 187 -> 190.
  - `web/src/lib/geojson.test.ts`: +1 (36 -> 37).
  - `web/src/components/TripDetails.test.tsx`: +2 (5 -> 7).
- Combined delta: +16 test cases.

## Planner Notes

1. The spec does not define what to do if one exact canonical name still maps to multiple merged station ids. This plan chooses the safety-preserving behavior: warn and skip that edge rather than create a cross-product of potentially unrelated footpaths.
2. The spec requires a mode icon but does not prescribe an icon library or glyph set. This plan uses accessible, dependency-free Unicode icons and keeps the mode in visible text; product design may substitute an icon system later without changing the reach schema.
3. “No map geometry change” conflicts slightly with the current `linesGeoJSON` design: it flattens per-train paths into one `LineString`, which can implicitly draw a straight bridge between different transfer terminals even when the transfer leg itself is filtered out. This plan's bounded interpretation is “do not generate a rail segment from the transfer object and do not add a dashed connector”; eliminating the implicit bridge would require a `MultiLineString`/multiple-feature geometry change and is left for item I.
4. “Build never fails” is interpreted as all semantic `[transfers]` resolution/validation failures warning and skipping, matching the existing `[cities]` unmatched-member policy. The existing project still treats globally malformed TOML syntax as a configuration error; the spec does not explicitly say to swallow `tomllib.TOMLDecodeError`.
5. The Appendix repeats Madrid because it describes replacing the existing group. Literal appending would create an invalid duplicate TOML key, so the plan removes the old Madrid line and pastes the complete approved fenced block contiguously after Roma; the shipped block itself remains byte-for-byte verbatim.
