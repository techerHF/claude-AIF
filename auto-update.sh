#!/usr/bin/env bash
# auto-update.sh
# 每分鐘由 cron 呼叫，偵測 GitHub 有新版本就自動更新並重啟 dashboard
# 路徑：~/ai-factory/auto-update.sh
# 設定方式：bash deploy.sh（會自動加入 cron）

cd ~/ai-factory || exit 1

REMOTE_SHA=$(git ls-remote origin HEAD 2>/dev/null | awk '{print $1}')
LOCAL_SHA=$(git rev-parse HEAD 2>/dev/null)
LOG=logs/auto-update.log

# 確保 log 目錄存在
mkdir -p logs

# 無法取得 remote SHA（網路問題）→ 靜默退出
[ -z "$REMOTE_SHA" ] && exit 0

# SHA 相同 → 無更新，靜默退出
[ "$REMOTE_SHA" = "$LOCAL_SHA" ] && exit 0

# 有更新 → 執行
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 偵測到新版本 ${REMOTE_SHA:0:7}（本地：${LOCAL_SHA:0:7}），開始更新..." >> "$LOG"

git fetch origin >> "$LOG" 2>&1
git pull --ff-only origin master >> "$LOG" 2>&1

if [ $? -ne 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ pull 失敗，跳過重啟" >> "$LOG"
  exit 1
fi

# 重啟 dashboard
DASHBOARD_PID=$(pgrep -f "python3.*dashboard.py" | head -1)
if [ -n "$DASHBOARD_PID" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 關閉舊 dashboard (PID=$DASHBOARD_PID)..." >> "$LOG"
  kill "$DASHBOARD_PID"
  sleep 2
fi

nohup python3 ~/ai-factory/dashboard.py >> logs/dashboard.log 2>&1 &
NEW_PID=$!

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 更新完成，dashboard 重啟 (PID=$NEW_PID)" >> "$LOG"
