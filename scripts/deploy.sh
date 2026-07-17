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
