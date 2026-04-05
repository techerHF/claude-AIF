#!/usr/bin/env bash
# agent-growth-update.sh
# 每個 agent 完成任務後自動更新成長記錄
# 用法：bash agent-growth-update.sh [agent-id] [success|failure] "[學到的事]"

AGENT_ID="${1:-}"
RESULT="${2:-}"   # success / failure
INSIGHT="${3:-}"  # 這次學到什麼（空白則跳過）

[ -z "$AGENT_ID" ] && exit 0
[ -z "$INSIGHT" ] && exit 0

GROWTH_FILE=~/ai-factory/.agent-growth/${AGENT_ID}.md
TODAY=$(date +%Y-%m-%d)

[ ! -f "$GROWTH_FILE" ] && { echo "WARN: 找不到 $GROWTH_FILE"; exit 0; }

python3 - <<EOF
from pathlib import Path
from datetime import datetime

f = Path('$GROWTH_FILE')
content = f.read_text(encoding='utf-8')
today = '$TODAY'
result = '$RESULT'
insight = r"""$INSIGHT"""
icon = '✅' if result == 'success' else '❌'

entry = f'\n- {today}（{icon}）：{insight}'

# 更新「已掌握的有效模式」區塊
marker = '## 發現的有效模式'
if marker in content:
    content = content.replace(marker, marker + entry, 1)
else:
    # 如果沒有這個區塊，加到「失敗記錄」前面
    fallback = '## 失敗記錄'
    if fallback in content:
        content = content.replace(fallback, f'{marker}{entry}\n\n{fallback}', 1)
    else:
        content += f'\n{marker}{entry}\n'

# 更新「上次執行時間」
import re
content = re.sub(r'(上次執行時間[：:]\s*).*', f'\\g<1>{today}', content)

# 遞增「本月執行次數」
def inc_count(m):
    try: return str(int(m.group(1)) + 1)
    except: return '1'
content = re.sub(r'^(\d+)$', inc_count, content, flags=re.MULTILINE)

f.write_text(content, encoding='utf-8')
print(f'{r"$AGENT_ID"} 成長記錄已更新 [{icon}]')
EOF
