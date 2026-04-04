#!/usr/bin/env bash
# error-recovery.sh
# 用途：錯誤捕捉、記錄、自動重試邏輯
# 使用：bash error-recovery.sh [最大重試次數] [指令...]
# 範例：bash error-recovery.sh 3 bash .claude/hooks/quality-check.sh article.md

set -euo pipefail

MAX_RETRY=${1:-3}
shift
COMMAND=("$@")

ERROR_LOG=~/ai-factory/logs/error.log
TIMESTAMP=$(date +%Y-%m-%dT%H:%M:%S)

mkdir -p ~/ai-factory/logs

if [ ${#COMMAND[@]} -eq 0 ]; then
  echo "使用方式：error-recovery.sh [最大重試次數] [指令...]"
  exit 1
fi

ATTEMPT=0
SUCCESS=0

while [ $ATTEMPT -lt "$MAX_RETRY" ]; do
  ATTEMPT=$(( ATTEMPT + 1 ))
  echo "第 $ATTEMPT 次嘗試：${COMMAND[*]}"

  if OUTPUT=$("${COMMAND[@]}" 2>&1); then
    echo "$OUTPUT"
    echo "成功（第 $ATTEMPT 次）"
    SUCCESS=1
    break
  else
    echo "失敗（第 $ATTEMPT 次）：$OUTPUT"
    {
      echo "[$TIMESTAMP] 嘗試 $ATTEMPT/$MAX_RETRY 失敗"
      echo "指令：${COMMAND[*]}"
      echo "錯誤：$OUTPUT"
      echo "---"
    } >> "$ERROR_LOG"

    if [ $ATTEMPT -lt "$MAX_RETRY" ]; then
      echo "等待 30 秒後重試..."
      sleep 30
    fi
  fi
done

if [ $SUCCESS -eq 0 ]; then
  echo "ERROR: 經過 $MAX_RETRY 次嘗試仍然失敗"
  echo "錯誤已記錄到 $ERROR_LOG"
  {
    echo "[$TIMESTAMP] 最終失敗：${COMMAND[*]}（共嘗試 $MAX_RETRY 次）"
  } >> "$ERROR_LOG"
  exit 1
fi

exit 0
