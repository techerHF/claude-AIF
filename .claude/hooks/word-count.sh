#!/usr/bin/env bash
# word-count.sh
# 用途：驗證字數是否在規定範圍內（排除程式碼區塊）
# 使用：bash word-count.sh [文章路徑]

set -euo pipefail

ARTICLE_PATH=$1

if [ -z "$ARTICLE_PATH" ] || [ ! -f "$ARTICLE_PATH" ]; then
  echo "REJECTED: 找不到文章 $ARTICLE_PATH"
  exit 1
fi

# 去除程式碼區塊後計算字數（使用 Python3 精確計算 CJK 字數）
CHAR_COUNT=$(python3 -c "
import re, sys

with open('$ARTICLE_PATH', 'r', encoding='utf-8') as f:
    content = f.read()

# 移除程式碼區塊
content = re.sub(r'\`\`\`.*?\`\`\`', '', content, flags=re.DOTALL)

# 計算字數（CJK字符 + 英文單字）
cjk = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', content))
en_words = len(re.findall(r'[a-zA-Z]+', content))
print(cjk + en_words)
")

TOTAL_CHAR=$(wc -m < "$ARTICLE_PATH")

echo "=== 字數報告 ==="
echo "純文字字數（不含程式碼）：$CHAR_COUNT"
echo "總字數（含程式碼）：$TOTAL_CHAR"

# 字數標準（與 quality-check.sh 一致）：
# 純文字：800–1500 字
# 含程式碼總字數：最多 5000 字

if [ "$CHAR_COUNT" -lt 800 ]; then
  echo "REJECTED: 純文字字數不足（$CHAR_COUNT，最少800字）"
  echo "需要再增加約 $(( 800 - CHAR_COUNT )) 字"
  exit 1
elif [ "$CHAR_COUNT" -gt 1500 ]; then
  echo "WARNING: 純文字字數偏多（$CHAR_COUNT，建議最多1500字）"
  echo "建議精簡約 $(( CHAR_COUNT - 1500 )) 字"
  exit 0
elif [ "$TOTAL_CHAR" -gt 5000 ]; then
  echo "REJECTED: 含程式碼總字數過多（$TOTAL_CHAR，上限5000字）"
  exit 1
else
  echo "APPROVED: 字數在範圍內（純文字 $CHAR_COUNT 字 / 含程式碼 $TOTAL_CHAR 字）"
  exit 0
fi
