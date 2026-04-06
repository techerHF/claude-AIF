#!/usr/bin/env bash
# diagnose-dashboard-deploy.sh
# 用途：系統化檢測 Dashboard 部署狀態（版本、進程、cron、遠端分支、對外頁面）
# 用法：
#   bash diagnose-dashboard-deploy.sh
#   PUBLIC_URL="https://example.com" bash diagnose-dashboard-deploy.sh

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

PORT="${DASHBOARD_PORT:-3000}"
PUBLIC_URL="${PUBLIC_URL:-}"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo master)"

FAILS=0
WARNS=0

pass() { echo "✅ $*"; }
warn() { echo "⚠️  $*"; WARNS=$((WARNS+1)); }
fail() { echo "❌ $*"; FAILS=$((FAILS+1)); }
section() { echo; echo "=== $* ==="; }

section "基本資訊"
echo "Repo: $BASE_DIR"
echo "Branch: $BRANCH"
echo "Port: $PORT"
if [ -n "$PUBLIC_URL" ]; then
  echo "Public URL: $PUBLIC_URL"
else
  echo "Public URL: (未提供，略過外網檢查)"
fi

section "Git 狀態檢查"
LOCAL_SHA="$(git rev-parse HEAD 2>/dev/null || true)"
REMOTE_SHA=""
if git fetch origin "$BRANCH" --quiet; then
  REMOTE_SHA="$(git rev-parse "origin/$BRANCH" 2>/dev/null || true)"
fi

if [ -n "$LOCAL_SHA" ]; then
  echo "Local SHA : $LOCAL_SHA"
else
  fail "無法取得本地 SHA"
fi
if [ -n "$REMOTE_SHA" ]; then
  echo "Remote SHA: $REMOTE_SHA"
else
  warn "無法取得遠端 SHA（可能無 origin/$BRANCH）"
fi

if [ -n "$LOCAL_SHA" ] && [ -n "$REMOTE_SHA" ]; then
  if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
    pass "本地與遠端分支一致"
  else
    fail "本地與遠端分支不一致（需確認是否已部署最新版）"
  fi
fi

DIRTY_FILES="$(git status --porcelain || true)"
if [ -n "$DIRTY_FILES" ]; then
  warn "工作樹有未提交變更，可能影響部署一致性"
  echo "$DIRTY_FILES"
else
  pass "工作樹乾淨"
fi

section "檔案版本檢查"
if grep -q 'AI 無人工廠 Dashboard v11' dashboard.py; then
  pass "dashboard.py 檔頭版本為 v11"
else
  fail "dashboard.py 檔頭不是 v11"
fi

if grep -q '<title>AI 無人工廠 v11</title>' dashboard.py; then
  pass "HTML title 為 v11"
else
  fail "HTML title 不是 v11"
fi

section "進程與本機服務檢查"
PIDS="$(ps -ef | grep -E 'python3 .*dashboard.py' | grep -v grep || true)"
if [ -n "$PIDS" ]; then
  pass "偵測到 dashboard.py 進程"
  echo "$PIDS"
else
  fail "找不到 dashboard.py 進程"
fi

LOCAL_TITLE="$(curl -s --max-time 8 "http://127.0.0.1:$PORT" | grep -o '<title>[^<]*</title>' | head -n 1 || true)"
if [ -n "$LOCAL_TITLE" ]; then
  pass "本機 HTTP 可回應"
  echo "Local title: $LOCAL_TITLE"
else
  fail "本機 HTTP 無回應或未取得 title（port=$PORT）"
fi

section "對外頁面檢查"
if [ -n "$PUBLIC_URL" ]; then
  PUBLIC_TITLE="$(curl -s --max-time 12 "$PUBLIC_URL/?v=$(date +%s)" | grep -o '<title>[^<]*</title>' | head -n 1 || true)"
  if [ -n "$PUBLIC_TITLE" ]; then
    pass "對外 URL 可回應"
    echo "Public title: $PUBLIC_TITLE"
    if [ "$LOCAL_TITLE" != "$PUBLIC_TITLE" ]; then
      warn "本機 title 與對外 title 不一致（可能是路由/快取/不同服務）"
    else
      pass "本機與對外 title 一致"
    fi
  else
    fail "對外 URL 無回應或無法取得 title"
  fi
else
  warn "未提供 PUBLIC_URL，略過對外檢查"
fi

section "自動更新腳本檢查"
if [ -f "$BASE_DIR/auto-update-dashboard.sh" ]; then
  pass "auto-update-dashboard.sh 存在"
else
  fail "auto-update-dashboard.sh 不存在"
fi

if [ -x "$BASE_DIR/auto-update-dashboard.sh" ]; then
  pass "auto-update-dashboard.sh 具可執行權限"
else
  fail "auto-update-dashboard.sh 無可執行權限"
fi

section "Cron 檢查"
CRON_CONTENT="$(crontab -l 2>/dev/null || true)"
if [ -z "$CRON_CONTENT" ]; then
  fail "crontab 為空或無法讀取"
else
  pass "crontab 可讀取"
fi

AUTO_COUNT="$(echo "$CRON_CONTENT" | grep -c 'auto-update-dashboard.sh' || true)"
RUN_COUNT="$(echo "$CRON_CONTENT" | grep -c 'run.sh >> .*logs/cron.log' || true)"
FDB_COUNT="$(echo "$CRON_CONTENT" | grep -c 'feedback-collector agent 收集昨日發文數據' || true)"

echo "auto-update entries : $AUTO_COUNT"
echo "run.sh entries      : $RUN_COUNT"
echo "feedback entries    : $FDB_COUNT"

if [ "$AUTO_COUNT" -eq 1 ]; then pass "auto-update 排程數量正確（1）"; else warn "auto-update 排程數量異常（建議=1）"; fi
if [ "$RUN_COUNT" -eq 1 ]; then pass "run.sh 排程數量正確（1）"; else warn "run.sh 排程數量異常（建議=1）"; fi
if [ "$FDB_COUNT" -eq 1 ]; then pass "feedback 排程數量正確（1）"; else warn "feedback 排程數量異常（建議=1）"; fi

section "摘要"
echo "Fail: $FAILS"
echo "Warn: $WARNS"

if [ "$FAILS" -gt 0 ]; then
  echo "RESULT: FAIL"
  exit 1
fi
echo "RESULT: PASS"
