# Pipeline QoL: stale-output pruning + parallel compute — design

Date: 2026-07-10. Approved by user (compact session, token-constrained).

## Problems

1. `ose compute` never clears `data/out/`; when a station's canonical id changes
   (Konstanz alias, 2026-07-09), its old `reach_*.json` lingers. The server derives
   `has_reach` from files on disk, so a stale file resurrects a dead station in search.
2. Compute is serial per-origin; the 2026-07-10 run took ~46 min (laptop on battery;
   mains runs were ~15–20 min). Per-origin work is independent — embarrassingly parallel.

## Design (both in `pipeline/compute.py`)

- **Pruning:** `compute_all` records every `reach_*.json` filename written this run;
  afterwards it deletes any other `reach_*.json` in `out_dir` (prints each).
  `stations.json`/`meta.json` untouched.
- **Parallelism:** `compute_all(graph_dir, out_dir, workers: int | None = None)`.
  Default `os.process_cpu_count()`; `workers=1` = serial in-process path (tests,
  debugging). Parallel path: `ProcessPoolExecutor` with an initializer that parses
  `trips.json` once per worker (no per-task pickling of the trip list; works under
  Python 3.14's forkserver default). The per-origin body is factored into
  `_write_reach(trips, station_id, out_dir, sample_date, now) -> int` (destination
  count, 0 = nothing written); workers write their own files and return
  `(station_id, n)`; the parent sets `has_reach`, prints progress, prunes.
  `ose compute` gains optional `--workers N`. One `now` timestamp per run is passed
  to workers, so outputs stay byte-identical to serial.

## Testing (TDD)

- Pruning: plant a fake stale `reach_9999999.json`, run `compute_all(workers=1)`,
  assert it is deleted and fresh files remain.
- Parallel equivalence: fixture graph, `workers=1` vs `workers=2`, reach-file JSON
  equal after dropping `computed_at` (timestamps differ across runs, not within).
