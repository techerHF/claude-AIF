#!/usr/bin/env bash
# duplicate-check.sh
# 用途：確認新主題是否與歷史文章重複
# 使用：bash duplicate-check.sh [主題關鍵字]
# 輸出：UNIQUE 或 DUPLICATE（附說明）

set -euo pipefail

TOPIC=${1:-}
# 優先用 CWD 相對路徑（腳本從 repo root 呼叫時有效）
# fallback 到 ~/ai-factory（VPS 直接呼叫時）
if [ -f "logs/progress.json" ]; then
  PROGRESS_FILE="logs/progress.json"
else
  PROGRESS_FILE="$HOME/ai-factory/logs/progress.json"
fi

if [ -z "$TOPIC" ]; then
  echo "使用方式：duplicate-check.sh [主題關鍵字]"
  exit 1
fi

[ ! -f "$PROGRESS_FILE" ] && echo "[]" > "$PROGRESS_FILE"

python3 - <<PYEOF
import json, sys

with open('$PROGRESS_FILE', encoding='utf-8') as f:
    data = json.load(f)

topic = '$TOPIC'.lower()
matches = [x for x in data if topic in x.get('title', '').lower()]

if matches:
    print('DUPLICATE')
    for m in matches:
        print(f"  已有：{m['date']} - {m['title']}")
    sys.exit(1)
else:
    print('UNIQUE')
    sys.exit(0)
PYEOF
