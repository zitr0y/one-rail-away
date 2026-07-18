# Server Deploy Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One interactive server-side script that deploys code (pull + rebuild web/api) and optionally runs the data pipeline, with stage-skipping for fast test runs.

**Architecture:** Two bash scripts versioned in this repo under `scripts/`, executed on the server from its checkout at `/home/aaron/docker/one-rail-away`. `run-trains-pipeline.sh` is the existing server cron script moved into the repo and extended with a `[fetch|build|compute]` stage argument; `deploy.sh` is a new interactive wrapper (pull → conditional image rebuilds → pipeline menu → summary). Cron is repointed at the repo copy.

**Tech Stack:** bash, docker compose, git. No test framework exists for shell in this repo — verification is `shellcheck` + `bash -n` locally and smoke tests on the server (spec's Testing section).

## Global Constraints

- Scripts live in `scripts/` in this repo; server runs them from `/home/aaron/docker/one-rail-away/scripts/`.
- `run-trains-pipeline.sh` with no argument must behave identically to today's `/home/aaron/run-trains-pipeline.sh` (cron compatibility): idle-slot build, `MIN_REACH_FILES=100` floor, atomic symlink flip, log to `/home/aaron/logs/trains-pipeline.log`, `nice -n 19 ionice -c 3` wrapper.
- `deploy.sh` is interactive-only (no flags, no non-interactive mode — YAGNI per spec).
- Change detection only picks prompt defaults; every prompt must be overridable.
- A failed pipeline run must not abort `deploy.sh` before its summary, and must leave the previous data slot live (guaranteed by the slot-flip design).
- Server host: `aaron@aaronbussche.eu`. Compose dir: `/home/aaron/docker`. Data dir: `/home/aaron/docker/trains-data`.

---

### Task 1: `scripts/run-trains-pipeline.sh` with stage argument

**Files:**
- Create: `scripts/run-trains-pipeline.sh` (mode 755)

**Interfaces:**
- Consumes: nothing from other tasks. Mirrors the current server script at `/home/aaron/run-trains-pipeline.sh` (content reproduced below — do not fetch it).
- Produces: `scripts/run-trains-pipeline.sh [fetch|build|compute]` (default `fetch`), exit 0 on published run, non-zero on abort/failure, exit 2 on bad argument. Task 2's `deploy.sh` calls it by this path and relies on these semantics.

- [ ] **Step 1: Write the script**

The original server script redirects the whole run to the log with `{ … } >> "$LOG" 2>&1`. Replace that with an `exec` redirect that tees to the terminal when stdout is a tty (so `deploy.sh` streams output) and appends silently under cron. Everything else is the original script plus the stage `case`.

```bash
#!/bin/bash
# Recompute one-rail-away data into the IDLE slot, then publish it with one
# atomic symlink flip. The live site keeps serving the old slot for the whole
# run, so a recompute never shows torn or half-written data, and a failed run
# leaves the previous data set untouched.
#
# The API reads its JSON from disk on every request and follows
# /app/data/out -> out-a|out-b, so publishing needs NO container restart.
#
# Run weekly via cron; safe to run by hand any time.
#
# Usage: run-trains-pipeline.sh [fetch|build|compute]
#   fetch    (default) full run: download feeds, build graph, compute
#   build    skip download; reuses data/raw/ from the previous run
#   compute  skip download and graph build; reuses data/raw/ and data/graph/
# Stage skipping works because the repo is bind-mounted at /app and only
# data/out is slot-mounted - raw feeds and the built graph persist across runs.
set -euo pipefail

STAGE="${1:-fetch}"
case "$STAGE" in
  fetch|build|compute) ;;
  *) echo "usage: $0 [fetch|build|compute]" >&2; exit 2 ;;
esac

LOG=/home/aaron/logs/trains-pipeline.log
DATA=/home/aaron/docker/trains-data
MIN_REACH_FILES=100   # sanity floor: refuse to publish an obviously broken run

mkdir -p /home/aaron/logs
[ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 5000000 ] && mv "$LOG" "$LOG.1"

# Under cron append silently to the log; at a terminal stream AND log.
if [ -t 1 ]; then
  exec > >(tee -a "$LOG") 2>&1
else
  exec >> "$LOG" 2>&1
fi

echo "=== pipeline run started $(date -Is) (stage: $STAGE) ==="
cd /home/aaron/docker

active=$(readlink "$DATA/out")
if [ "$active" = "out-a" ]; then next=out-b; else next=out-a; fi
echo "live slot: $active  ->  building into: $next"

rm -rf "${DATA:?}/${next:?}"
mkdir -p "$DATA/$next"

# Writes ONLY into the idle slot (bind-mounted over /app/data/out). The
# fetch stage uses the image's default CMD; later stages override the
# command with the same nice/ionice + uv invocation minus earlier stages.
case "$STAGE" in
  fetch)
    docker compose run --rm -v "$DATA/$next:/app/data/out" trains-pipeline
    ;;
  build)
    docker compose run --rm -v "$DATA/$next:/app/data/out" trains-pipeline \
      sh -c "nice -n 19 ionice -c 3 sh -c 'uv sync --frozen --no-dev && uv run --frozen --no-dev ose build && uv run --frozen --no-dev ose compute'"
    ;;
  compute)
    docker compose run --rm -v "$DATA/$next:/app/data/out" trains-pipeline \
      sh -c "nice -n 19 ionice -c 3 sh -c 'uv sync --frozen --no-dev && uv run --frozen --no-dev ose compute'"
    ;;
esac

test -s "$DATA/$next/stations.json" || { echo "ABORT: no stations.json"; exit 1; }
n=$(find "$DATA/$next" -maxdepth 1 -name "reach_*.json" | wc -l)
if [ "$n" -lt "$MIN_REACH_FILES" ]; then
  echo "ABORT: only $n reach files (floor $MIN_REACH_FILES). Keeping $active live."
  exit 1
fi

# Atomic publish: rename(2) swaps the symlink in a single syscall. No window
# exists in which /app/data/out is missing or points at a partial data set.
ln -sfnT "$next" "$DATA/out.tmp"
mv -fT "$DATA/out.tmp" "$DATA/out"

echo "PUBLISHED: out -> $next  ($n reach files)"
echo "=== pipeline run finished OK $(date -Is) ==="
```

- [ ] **Step 2: Make it executable and lint**

Run: `chmod +x scripts/run-trains-pipeline.sh && bash -n scripts/run-trains-pipeline.sh && shellcheck scripts/run-trains-pipeline.sh`
Expected: no output (shellcheck clean). If shellcheck is not installed locally, `bash -n` alone is acceptable; note it in the commit message.

- [ ] **Step 3: Test the argument guard locally**

Run: `bash scripts/run-trains-pipeline.sh bogus; echo "exit=$?"`
Expected: `usage: scripts/run-trains-pipeline.sh [fetch|build|compute]` on stderr, `exit=2`. (The guard fires before any server path is touched, so this is safe to run locally.)

- [ ] **Step 4: Commit**

```bash
git add scripts/run-trains-pipeline.sh
git commit -m "feat(ops): version pipeline cron script in repo, add stage-skip argument"
```

---

### Task 2: `scripts/deploy.sh` interactive all-in-one deploy

**Files:**
- Create: `scripts/deploy.sh` (mode 755)

**Interfaces:**
- Consumes: `scripts/run-trains-pipeline.sh [fetch|build|compute]` from Task 1 (called via the script's own directory, exit 0 = published).
- Produces: `scripts/deploy.sh`, run manually on the server, no arguments.

- [ ] **Step 1: Write the script**

```bash
#!/bin/bash
# All-in-one interactive deploy for onestopeurope, run ON THE SERVER:
#   pull -> rebuild trains-web / trains-api (defaults from what changed)
#        -> optional pipeline run (full / skip download / skip to compute)
#        -> summary.
# Change detection only picks the prompt DEFAULTS - every step can be
# forced or skipped by answering the prompt.
set -euo pipefail

REPO=/home/aaron/docker/one-rail-away
COMPOSE_DIR=/home/aaron/docker
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

prompt_yn() {  # $1 = question (shown verbatim), $2 = default answer y|n
  local ans
  read -r -p "$1 " ans
  ans="${ans:-$2}"
  [[ "$ans" =~ ^[Yy] ]]
}

cd "$REPO"
echo "== Pulling $REPO"
old_head=$(git rev-parse HEAD)
git pull --ff-only
new_head=$(git rev-parse HEAD)

web_changed=no
api_changed=no
if [ "$old_head" != "$new_head" ]; then
  echo "-- pulled $(git rev-list --count "$old_head..$new_head") commit(s):"
  git log --oneline "$old_head..$new_head" | sed 's/^/     /'
  changed=$(git diff --name-only "$old_head" "$new_head")
  if grep -q '^web/' <<<"$changed"; then web_changed=yes; fi
  if grep -q '^server/' <<<"$changed"; then api_changed=yes; fi
else
  echo "-- already up to date"
fi

rebuild_service() {  # $1 = service name, $2 = changed yes|no; echoes result
  local q d
  if [ "$2" = yes ]; then
    q="-> $1 source changed: rebuild? [Y/n]"; d=y
  else
    q="-> $1 unchanged: rebuild anyway? [y/N]"; d=n
  fi
  if prompt_yn "$q" "$d"; then
    (cd "$COMPOSE_DIR" && docker compose build "$1" && docker compose up -d "$1") >&2
    echo rebuilt
  else
    echo skipped
  fi
}

web_result=$(rebuild_service trains-web "$web_changed")
api_result=$(rebuild_service trains-api "$api_changed")

echo "Run pipeline?  [1] full  [2] from build (skip download)  [3] from compute  [4] skip"
read -r -p "> " choice
choice="${choice:-4}"
case "$choice" in
  1) stage=fetch ;;
  2) stage=build ;;
  3) stage=compute ;;
  *) stage="" ;;
esac

pipeline_result=skipped
if [ -n "$stage" ]; then
  # Streams to the terminal AND appends to the usual log (the pipeline
  # script tees when stdout is a tty). A failure must not kill deploy.sh:
  # the slot flip guarantees the previous data set is still live.
  if "$SCRIPT_DIR/run-trains-pipeline.sh" "$stage"; then
    pipeline_result="OK (stage: $stage)"
  else
    pipeline_result="FAILED (stage: $stage) - previous data still live, see ~/logs/trains-pipeline.log"
  fi
fi

bundle=$(docker exec aaron-trains-web sh -c \
  "grep -oE 'index-[A-Za-z0-9_-]+\.js' /usr/share/nginx/html/index.html" \
  2>/dev/null || echo "unknown (trains-web not running?)")

echo
echo "== Summary"
echo "   commits:    ${old_head:0:7} -> ${new_head:0:7}"
echo "   trains-web: $web_result"
echo "   trains-api: $api_result"
echo "   pipeline:   $pipeline_result"
echo "   serving:    $bundle"
```

- [ ] **Step 2: Make it executable and lint**

Run: `chmod +x scripts/deploy.sh && bash -n scripts/deploy.sh && shellcheck scripts/deploy.sh`
Expected: no output. Shellcheck may warn SC2312 (masked return in `$(rebuild_service …)`) depending on version/strictness — informational only; fix any error-level findings.

- [ ] **Step 3: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat(ops): interactive all-in-one server deploy script"
```

---

### Task 3: Server rollout — cron repoint and smoke test

This task runs against the live server. It changes cron and deletes the old script copy only after the repo copy is verified present and executable.

**Files:**
- Modify (server): crontab for user `aaron`
- Delete (server): `/home/aaron/run-trains-pipeline.sh` (after cron repoint)

**Interfaces:**
- Consumes: both scripts from Tasks 1–2, pushed to `origin/main`.
- Produces: server cron line `30 4 * * 1 /home/aaron/docker/one-rail-away/scripts/run-trains-pipeline.sh`.

- [ ] **Step 1: Push and pull on the server**

```bash
git push
ssh aaron@aaronbussche.eu 'cd ~/docker/one-rail-away && git pull --ff-only && ls -la scripts/'
```
Expected: both scripts listed with `-rwxr-xr-x` (git preserves the exec bit).

- [ ] **Step 2: Repoint cron, then delete the old copy**

```bash
ssh aaron@aaronbussche.eu 'crontab -l | sed "s|/home/aaron/run-trains-pipeline.sh|/home/aaron/docker/one-rail-away/scripts/run-trains-pipeline.sh|" | crontab - && crontab -l | grep trains && rm /home/aaron/run-trains-pipeline.sh'
```
Expected output: `30 4 * * 1 /home/aaron/docker/one-rail-away/scripts/run-trains-pipeline.sh`

- [ ] **Step 3: Smoke test deploy.sh (all-skip path)**

The user runs this interactively (it needs a tty):
```bash
ssh -t aaron@aaronbussche.eu '~/docker/one-rail-away/scripts/deploy.sh'
```
Answer `n` / `n` / `4`. Expected: "already up to date", both rebuild prompts default to No, pipeline skipped, summary shows the current `index-*.js` bundle hash.

- [ ] **Step 4: Verify a stage-skipping pipeline run**

From the smoke-test session (or a rerun), choose option `3` (from compute). This is the long pole — compute takes a while; it can run unattended since a failure keeps the previous slot live.
Expected in `~/logs/trains-pipeline.log`: `(stage: compute)` in the start line, no `ose fetch`/`ose build` output, and either `PUBLISHED: out -> out-…` or an `ABORT` that leaves the old slot live.

- [ ] **Step 5: Close out**

Confirm with the user, then note in the backlog/docs if desired. The first full cron run (next Monday 04:30) should be checked in `~/logs/trains-pipeline.log` — flagged in the spec's Testing section.
```bash
git log --oneline -3   # sanity: both feat(ops) commits present and pushed
```
