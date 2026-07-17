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

# Never allow two runs to race for the same idle slot (double-launch incident
# 2026-07-17: two runs 19s apart both built into out-a).
exec 9>/home/aaron/logs/trains-pipeline.lock
flock -n 9 || { echo "ABORT: another pipeline run is already active"; exit 1; }

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
