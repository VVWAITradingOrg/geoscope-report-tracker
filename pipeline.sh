#!/bin/bash
# geoscope-report-tracker — production entrypoint. Exits non-zero on any failed step.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
# Charge Codex model usage to the ljianhui100 ChatGPT profile.
export CODEX_HOME="/Users/vvw/.codex-w"
set -a
source config/settings.env
set +a

DELIVER=1
NOTIFY_CHANNEL="${MONITOR_CHANNEL:-channel:1476024801415008448}"
while [ $# -gt 0 ]; do
  case "$1" in
    --no-deliver) DELIVER=0; NOTIFY_CHANNEL="none" ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

JOB="geoscope-report-tracker"
LOCK="$DIR/state/pipeline.lock"
mkdir -p "$DIR/logs" "$DIR/state" "$DIR/output"

if ! mkdir "$LOCK" 2>/dev/null; then echo "pipeline already running" >&2; exit 3; fi
trap 'ec=$?; rmdir "$LOCK" 2>/dev/null || true; if [ $ec -ne 0 ]; then bash "$DIR/report.sh" "$JOB" fail "step=${STEP:-unknown} exit=$ec" none "$NOTIFY_CHANNEL"; fi; exit $ec' EXIT

RUN_ID="$(TZ="$TIMEZONE" date +%Y-%m-%d-%H%M%S)"
RUN_DIR="$DIR/output/$RUN_ID"
mkdir -p "$RUN_DIR"

bash "$DIR/report.sh" "$JOB" running "run=$RUN_ID" none

STEP="fetch"
/usr/bin/python3 scripts/fetch.py --run-dir "$RUN_DIR"

STEP="analyze"
/usr/bin/python3 scripts/analyze.py --run-dir "$RUN_DIR"

READY_COUNT="$(/usr/bin/python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$RUN_DIR/ready.json")"
if [ "$READY_COUNT" = "0" ]; then
  ln -sfn "$RUN_DIR" "$DIR/output/latest"
  bash "$DIR/report.sh" "$JOB" ok "run=$RUN_ID nothing new" none "$NOTIFY_CHANNEL"
  trap - EXIT
  rmdir "$LOCK"
  echo "OK run_dir=$RUN_DIR nothing_new=1"
  exit 0
fi

STEP="validate"
/usr/bin/python3 scripts/validate.py --run-dir "$RUN_DIR"

STEP="render"
/usr/bin/python3 scripts/render.py --run-dir "$RUN_DIR"

ln -sfn "$RUN_DIR" "$DIR/output/latest"

STEP="deliver"
if [ "$DELIVER" = "1" ]; then
  /usr/bin/python3 scripts/deliver.py --run-dir "$RUN_DIR" --account "$DISCORD_ACCOUNT"
fi

bash "$DIR/report.sh" "$JOB" ok "run=$RUN_ID delivered=$READY_COUNT deliver=$DELIVER" none "$NOTIFY_CHANNEL"
trap - EXIT
rmdir "$LOCK"
echo "OK run_dir=$RUN_DIR delivered=$READY_COUNT deliver=$DELIVER"
