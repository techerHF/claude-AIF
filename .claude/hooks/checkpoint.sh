#!/usr/bin/env bash
# checkpoint.sh
# 用途：記錄和查詢文章生產進度
# 使用：
#   checkpoint.sh log [標題] [狀態]  → 記錄
#   checkpoint.sh status             → 今日狀態
#   checkpoint.sh list               → 最近10筆
#   checkpoint.sh today-done         → 今日是否完成（輸出 0 或 1）

set -euo pipefail

PROGRESS_FILE=~/ai-factory/logs/progress.json
TODAY=$(date +%Y-%m-%d)

mkdir -p ~/ai-factory/logs
[ ! -f "$PROGRESS_FILE" ] && echo "[]" > "$PROGRESS_FILE"

case ${1:-} in
  "log")
    TITLE=${2:-unknown}
    STATUS=${3:-draft}
    TIMESTAMP=$(date +%Y-%m-%dT%H:%M:%S)

    python3 - <<PYEOF
import json
with open('$PROGRESS_FILE', 'r', encoding='utf-8') as f:
    data = json.load(f)
data.append({
    'date': '$TODAY',
    'timestamp': '$TIMESTAMP',
    'title': '$TITLE',
    'status': '$STATUS'
})
# 只保留最近200筆
if len(data) > 200:
    data = data[-200:]
with open('$PROGRESS_FILE', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('已記錄：$TITLE [$STATUS]')
PYEOF
    ;;

  "status")
    echo "=== 今日進度（$TODAY）==="
    python3 - <<PYEOF
import json
with open('$PROGRESS_FILE', encoding='utf-8') as f:
    data = json.load(f)
today = [x for x in data if x.get('date') == '$TODAY']
if not today:
    print('今日尚無記錄')
else:
    for item in today:
        print(f"[{item['status']}] {item['title']} @ {item.get('timestamp','')}")
PYEOF
    ;;

  "list")
    echo "=== 最近10筆記錄 ==="
    python3 - <<PYEOF
import json
with open('$PROGRESS_FILE', encoding='utf-8') as f:
    data = json.load(f)
recent = data[-10:] if len(data) > 10 else data
for item in reversed(recent):
    print(f"{item['date']} [{item['status']}] {item['title']}")
PYEOF
    ;;

  "today-done")
    python3 - <<PYEOF
import json
with open('$PROGRESS_FILE', encoding='utf-8') as f:
    data = json.load(f)
today_posted = [x for x in data if x.get('date') == '$TODAY' and x.get('status') in ('posted', 'reviewed')]
print(1 if today_posted else 0)
PYEOF
    ;;

  *)
    echo "使用方式："
    echo "  checkpoint.sh log [標題] [狀態]"
    echo "  checkpoint.sh status"
    echo "  checkpoint.sh list"
    echo "  checkpoint.sh today-done"
    ;;
esac
