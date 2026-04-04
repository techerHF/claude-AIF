#!/usr/bin/env bash
# memory-update.sh
# 用途：每次執行後更新 CLAUDE.md 的記錄欄位
# 使用：bash memory-update.sh [標題] [狀態] [subreddit]

set -euo pipefail

TITLE=${1:-}
STATUS=${2:-draft}
SUBREDDIT=${3:-}
TODAY=$(date +%Y-%m-%d)
CLAUDE_MD=~/ai-factory/CLAUDE.md

if [ -z "$TITLE" ]; then
  echo "使用方式：memory-update.sh [標題] [狀態] [subreddit]"
  exit 1
fi

if [ ! -f "$CLAUDE_MD" ]; then
  echo "ERROR: 找不到 $CLAUDE_MD"
  exit 1
fi

# 備份
cp "$CLAUDE_MD" "$CLAUDE_MD.bak"

NEW_RECORD="- $TODAY：$TITLE [$STATUS]$([ -n "$SUBREDDIT" ] && echo " → $SUBREDDIT" || true)"

python3 - <<PYEOF
with open('$CLAUDE_MD', 'r', encoding='utf-8') as f:
    content = f.read()

marker = '## 已發文記錄'
if marker in content:
    parts = content.split(marker, 1)
    updated = parts[0] + marker + '\n$NEW_RECORD\n' + parts[1]
    with open('$CLAUDE_MD', 'w', encoding='utf-8') as f:
        f.write(updated)
    print('CLAUDE.md 已發文記錄已更新')
else:
    print('WARNING: 找不到已發文記錄區塊')

with open('$CLAUDE_MD', 'r', encoding='utf-8') as f:
    content = f.read()

marker2 = '## 已使用主題記錄'
if marker2 in content:
    parts2 = content.split(marker2, 1)
    updated2 = parts2[0] + marker2 + '\n- $TODAY：$TITLE\n' + parts2[1]
    with open('$CLAUDE_MD', 'w', encoding='utf-8') as f:
        f.write(updated2)
    print('CLAUDE.md 主題記錄已更新')
PYEOF
