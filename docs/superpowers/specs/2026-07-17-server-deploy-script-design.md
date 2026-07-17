# Server deploy script — design

**Date:** 2026-07-17
**Status:** approved approach (A), spec for review

## Problem

Deploying has three independent moving parts on the server (git pull, web/api
image rebuild, pipeline run), and forgetting one produces silent partial
deploys — e.g. 2026-07-17: pipeline rerun picked up curve data but the web
container kept serving a pre-heat-strip bundle. There is also no way to run
the pipeline without re-downloading all feeds, which makes server-side
testing slow.

## Solution overview

Two scripts, both versioned in this repo under `scripts/`, run on the server
from its checkout at `~/docker/one-rail-away`:

1. **`scripts/run-trains-pipeline.sh`** — the existing
   `/home/aaron/run-trains-pipeline.sh` moved into the repo, extended with an
   optional stage argument. Cron is updated to call the repo path.
2. **`scripts/deploy.sh`** — new interactive all-in-one deploy, invoked by
   sshing to the server and running it.

## `run-trains-pipeline.sh` changes

Signature: `run-trains-pipeline.sh [fetch|build|compute]` (default `fetch`).

- `fetch` — full run, byte-identical behavior to today: default container CMD
  (`ose fetch && ose build && ose compute`).
- `build` — skip download. Overrides the compose command to run
  `uv sync … && ose build && ose compute`. Relies on `data/raw/` persisting in
  the repo bind-mount (it does — only `data/out` is slot-bind-mounted).
- `compute` — skip download and graph build; runs `ose compute` only. Relies
  on `data/graph/` persisting (it does, same reason).

Everything else is untouched: idle-slot build, `MIN_REACH_FILES` sanity floor,
atomic symlink flip, logging to `~/logs/trains-pipeline.log`. The stage
override only changes the command passed to `docker compose run`. The `nice`/
`ionice` wrapper is preserved for all stages.

Cron line becomes:
`30 4 * * 1 /home/aaron/docker/one-rail-away/scripts/run-trains-pipeline.sh`
(no argument → full run, unchanged behavior). The old copy in `~` is deleted
after the cron edit.

## `deploy.sh` behavior

Runs on the server; interactive prompts (this was an explicit choice). Steps:

1. `git -C ~/docker/one-rail-away pull --ff-only`; abort on non-ff. Show the
   pulled commit range and a summary of changed top-level areas.
2. **Web:** if `web/` changed in the pulled range, prompt
   `rebuild trains-web? [Y/n]`; if nothing pulled or `web/` unchanged, prompt
   with default No. Rebuild = `docker compose build trains-web && docker
   compose up -d trains-web` in `~/docker`.
3. **API:** same logic for `server/` → `trains-api`.
4. **Pipeline:** prompt
   `Run pipeline? [1] full  [2] from build (skip download)  [3] from compute  [4] skip`
   (default: skip). Choices 1–3 exec `scripts/run-trains-pipeline.sh` with the
   matching stage; output streams to the terminal *and* appends to the usual
   log (`tee -a`).
5. Final summary: what was rebuilt, what was skipped, pipeline result,
   currently served bundle hash (`curl` the local container's index.html).

Notes:
- Change detection is a default-answer aid only; every prompt can be
  overridden, so a stale detection heuristic can never block a deploy.
- No flags/non-interactive mode for now (YAGNI — cron uses the pipeline
  script directly, not deploy.sh).
- Pipeline *image* rebuilds are out of scope: the container mounts the repo
  and `uv sync`s at start, so pipeline code changes need no image rebuild.
  Dockerfile/compose changes remain a manual `docker compose build
  trains-pipeline`.

## Error handling

- `set -euo pipefail` in both scripts.
- deploy.sh aborts before any rebuild if the pull fails.
- A failed pipeline run keeps the previous data slot live (existing
  slot-flip guarantee) and deploy.sh reports the failure in its summary
  instead of dying silently mid-script.

## Testing

- Shellcheck both scripts.
- On the server: run `deploy.sh` with no new commits (all-skip path), then a
  `compute`-stage pipeline run to verify command override + publish still
  works, then confirm cron entry parses (`crontab -l`).
- Verify a full weekly cron run the following Monday (log check).

## Out of scope

- Versioning the `~/docker/trains/*.Dockerfile` + `nginx.conf` build context
  (server-only today; worth doing separately — the nginx cache-header fix of
  2026-07-17 lives only there).
- Local `just deploy` wrapper (explicitly declined; can be added later as a
  one-liner).
