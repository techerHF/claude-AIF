#!/usr/bin/env bash
# auto-update-dashboard.sh
# 用途：在 VPS 週期性自動更新程式碼，若有新 commit 則重啟 dashboard

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

LOG_FILE="$BASE_DIR/logs/auto-update.log"
mkdir -p "$BASE_DIR/logs"

now() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(now)] $*" >> "$LOG_FILE"; }

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "master")
REMOTE_REF="origin/$BRANCH"

if ! git fetch origin "$BRANCH" --quiet; then
  log "WARN: git fetch 失敗（branch=$BRANCH）"
  exit 0
fi

LOCAL_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")
REMOTE_SHA=$(git rev-parse "$REMOTE_REF" 2>/dev/null || echo "")

if [ -z "$LOCAL_SHA" ] || [ -z "$REMOTE_SHA" ]; then
  log "WARN: 無法取得 commit SHA（local=$LOCAL_SHA remote=$REMOTE_SHA）"
  exit 0
fi

if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
  log "OK: 無新版本（$LOCAL_SHA）"
  exit 0
fi

log "INFO: 偵測到新版本，準備更新（$LOCAL_SHA -> $REMOTE_SHA）"

if ! git pull --ff-only origin "$BRANCH" >> "$LOG_FILE" 2>&1; then
  log "ERROR: git pull 失敗，略過本次重啟"
  exit 0
fi

# 關閉舊程序（若不存在不視為錯誤）
pkill -f "python3 .*dashboard.py" >/dev/null 2>&1 || true
sleep 1

# 重新啟動 dashboard
nohup python3 "$BASE_DIR/dashboard.py" >> "$BASE_DIR/logs/dashboard.log" 2>&1 &
NEW_PID=$!

log "INFO: dashboard 已重啟（pid=$NEW_PID）"
