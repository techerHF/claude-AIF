#!/usr/bin/env bash
# reddit-rate-limit.sh
# 用途：確認發文頻率不超過限制（每板每週最多2篇）
# 使用：bash reddit-rate-limit.sh [subreddit名稱]

set -euo pipefail

SUBREDDIT=${1:-}
# 相容本地開發（CWD = repo root）和 VPS 直接呼叫
if [ -d "logs" ]; then
  REDDIT_LOG="logs/reddit-history.json"
else
  mkdir -p "$HOME/ai-factory/logs"
  REDDIT_LOG="$HOME/ai-factory/logs/reddit-history.json"
fi
[ ! -f "$REDDIT_LOG" ] && echo "[]" > "$REDDIT_LOG"

if [ -z "$SUBREDDIT" ]; then
  echo "使用方式：reddit-rate-limit.sh [subreddit]"
  exit 1
fi

python3 - <<PYEOF
import json, sys
from datetime import datetime, timedelta

with open('$REDDIT_LOG', encoding='utf-8') as f:
    data = json.load(f)

week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
this_week = [
    x for x in data
    if x.get('subreddit') == '$SUBREDDIT'
    and x.get('date', '') >= week_ago
]

count = len(this_week)
if count >= 2:
    print(f'BLOCKED: r/$SUBREDDIT 本週已發 {count} 篇，已達上限（每週最多2篇）')
    for item in this_week:
        print(f"  - {item['date']}: {item.get('title', '')}")
    sys.exit(1)
else:
    print(f'ALLOWED: r/$SUBREDDIT 本週已發 {count} 篇，還可以發 {2-count} 篇')
    sys.exit(0)
PYEOF
