#!/usr/bin/env bash
# keepalive.sh
# 防止 SSH 因為沒有輸出而斷線
# 用法：bash keepalive.sh &   KEEPALIVE_PID=$!   （測試結束後 kill $KEEPALIVE_PID）

INTERVAL=${1:-30}  # 預設每30秒
while true; do
  echo "[keepalive] $(date '+%H:%M:%S') — 後台運作中..."
  sleep "$INTERVAL"
done
