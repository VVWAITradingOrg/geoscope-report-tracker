#!/bin/bash
# 状态上报 + Discord 通知（异常/失败才发 Discord，正常心跳只写本地文件）。
#
# 用法:
#   report.sh <job> running [session]
#   report.sh <job> ok      <message> [session] [channel]
#   report.sh <job> fail    <message> [session] [channel]
set -uo pipefail

JOB="${1:?用法: report.sh <job> running|ok|fail ...}"
EVENT="${2:?缺少事件类型: running|ok|fail}"
MSG="${3:-}"
SESSION="${4:-}"
CHANNEL="${5:-}"

STATUS_DIR="$HOME/.openclaw/task-status"
mkdir -p "$STATUS_DIR"
HEARTBEAT="$STATUS_DIR/$JOB.json"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

MONITOR_CHANNEL="${MONITOR_CHANNEL:-channel:1476024801415008448}"

json_escape() {
  /usr/bin/python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

write_heartbeat() {
  local status="$1" step="$2"
  local msg_json session_json
  msg_json="$(json_escape "$step")"
  session_json="$(json_escape "$SESSION")"
  cat > "$HEARTBEAT" <<EOF
{"job":"$JOB","status":"$status","session":$session_json,"step":$msg_json,"ts":"$NOW"}
EOF
}

send_discord() {
  local channel="$1" text="$2"
  if [ "$channel" = "none" ]; then
    return 0
  fi
  local target="${channel:-$MONITOR_CHANNEL}"
  if ! openclaw message send --channel discord --account default --target "$target" --message "$text" >/dev/null 2>>"$STATUS_DIR/$JOB-send-errors.log"; then
    echo "[report.sh] 警告: 发送到 $target 失败，见 $STATUS_DIR/$JOB-send-errors.log" >&2
  fi
}

case "$EVENT" in
  running)
    write_heartbeat "running" "$MSG"
    ;;
  ok)
    write_heartbeat "ok" "$MSG"
    send_discord "$CHANNEL" "✅ [$JOB${SESSION:+/$SESSION}] $MSG"
    ;;
  fail)
    write_heartbeat "fail" "$MSG"
    send_discord "${CHANNEL:-$MONITOR_CHANNEL}" "🔴 [$JOB${SESSION:+/$SESSION}] 失败: $MSG"
    ;;
  *)
    echo "未知事件: $EVENT (应为 running|ok|fail)" >&2
    exit 1
    ;;
esac
