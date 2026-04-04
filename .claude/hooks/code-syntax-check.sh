#!/usr/bin/env bash
# code-syntax-check.sh
# 用途：驗證文章內程式碼區塊的完整性
# 使用：bash code-syntax-check.sh [文章路徑]

set -euo pipefail

ARTICLE_PATH=$1
RESULT="APPROVED"
CODE_ISSUES=""

if [ -z "$ARTICLE_PATH" ] || [ ! -f "$ARTICLE_PATH" ]; then
  echo "REJECTED: 找不到文章 $ARTICLE_PATH"
  exit 1
fi

CONTENT=$(cat "$ARTICLE_PATH")

# 檢查1-3：使用 Python3 計算程式碼區塊（避免 bash backtick 解析衝突）
CODE_CHECK=$(python3 - "$ARTICLE_PATH" <<'PYEOF'
import sys, re

path = sys.argv[1]
with open(path, encoding='utf-8') as f:
    content = f.read()

# 計算以 ``` 開頭的行數
backtick_lines = [l for l in content.splitlines() if l.startswith('```')]
count = len(backtick_lines)

issues = []
if count < 2:
    issues.append(f"沒有程式碼區塊（找到 {count} 個 backtick 行，至少需要2個）")
if count % 2 != 0:
    issues.append(f"程式碼區塊未正確關閉（共 {count} 個，需要成對）")

# 檢查省略符號
if re.search(r'^\s*\.\.\.\s*$', content, re.MULTILINE):
    issues.append("程式碼有省略（...），必須提供完整程式碼")

print(f"BLOCK_COUNT={count // 2 if count >= 2 else 0}")
for issue in issues:
    print(f"ISSUE={issue}")
PYEOF
)

BLOCK_COUNT=$(echo "$CODE_CHECK" | grep '^BLOCK_COUNT=' | cut -d= -f2)
while IFS= read -r line; do
  if [[ "$line" == ISSUE=* ]]; then
    RESULT="REJECTED"
    CODE_ISSUES="$CODE_ISSUES\n- ${line#ISSUE=}"
  fi
done <<< "$CODE_CHECK"

# 檢查4：Arduino 程式碼必要元素（直接在全文搜尋，避免 awk 分段問題）
if echo "$CONTENT" | grep -q '```arduino'; then
  if ! echo "$CONTENT" | grep -q "void setup"; then
    RESULT="REJECTED"
    CODE_ISSUES="$CODE_ISSUES\n- Arduino 程式碼缺少 setup() 函式"
  fi

  if ! echo "$CONTENT" | grep -q "void loop"; then
    RESULT="REJECTED"
    CODE_ISSUES="$CODE_ISSUES\n- Arduino 程式碼缺少 loop() 函式"
  fi
fi

# 檢查5：程式碼有注解（至少3行 //）
COMMENT_COUNT=$(echo "$CONTENT" | grep -c '//' || true)
if [ "$COMMENT_COUNT" -lt 3 ]; then
  RESULT="REJECTED"
  CODE_ISSUES="$CODE_ISSUES\n- 程式碼注解不足（少於3行），需要說明關鍵步驟"
fi

# 輸出結果
if [ "$RESULT" = "APPROVED" ]; then
  echo "APPROVED: 程式碼結構完整"
  echo "程式碼區塊數量：${BLOCK_COUNT:-0}"
  echo "注解行數：$COMMENT_COUNT"
else
  echo "REJECTED: 程式碼有問題"
  echo -e "問題清單：$CODE_ISSUES"
fi
