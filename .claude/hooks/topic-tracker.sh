#!/usr/bin/env bash
# topic-tracker.sh
# 用途：追蹤已用主題，建議下一個選題
# 使用：
#   topic-tracker.sh suggest   → 建議下一個主題類別
#   topic-tracker.sh history   → 顯示主題歷史

set -euo pipefail

PROGRESS_FILE=~/ai-factory/logs/progress.json
[ ! -f "$PROGRESS_FILE" ] && echo "[]" > "$PROGRESS_FILE"

case ${1:-} in
  "suggest")
    python3 - <<'PYEOF'
import json

PROGRESS_FILE = '/root/ai-factory/logs/progress.json'
try:
    with open(PROGRESS_FILE, encoding='utf-8') as f:
        data = json.load(f)
except FileNotFoundError:
    data = []

categories = {
    'A': ['電容式感測', '電阻式感測', '矩陣感測', '多軸力量感測', '壓力感測'],
    'B': ['壓力密碼', '手勢辨識', '觸覺回饋', '防窺視'],
    'C': ['PCB設計', '訊號處理', '矩陣掃描電路', '低功耗設計'],
    'D': ['PDMS製程', '銅箔電極', '3D列印結構', '軟性電路']
}

category_count = {k: 0 for k in categories}
all_titles = [x.get('title', '') for x in data]

for title in all_titles:
    for cat, topics in categories.items():
        if any(t in title for t in topics):
            category_count[cat] += 1

suggested_cat = min(category_count, key=category_count.get)
suggested_topics = categories[suggested_cat]

print(f'建議類別：{suggested_cat}類（已使用 {category_count[suggested_cat]} 次）')
print(f'可用主題：')
for t in suggested_topics:
    used = any(t in title for title in all_titles)
    status = '（已用）' if used else '（可用）'
    print(f'  - {t} {status}')
PYEOF
    ;;

  "history")
    echo "=== 主題使用歷史（最近20筆）==="
    python3 - <<PYEOF
import json
with open('$PROGRESS_FILE', encoding='utf-8') as f:
    data = json.load(f)
for item in data[-20:]:
    print(f"{item.get('date','?')}: {item.get('title','?')}")
PYEOF
    ;;

  *)
    echo "使用方式："
    echo "  topic-tracker.sh suggest"
    echo "  topic-tracker.sh history"
    ;;
esac
