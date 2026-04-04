#!/usr/bin/env bash
# ai-detection.sh
# 用途：偵測文章是否有明顯 AI 生成痕跡
# 使用：bash ai-detection.sh [文章路徑]

set -euo pipefail

ARTICLE_PATH=$1
RESULT="APPROVED"
AI_PATTERNS=""

if [ -z "$ARTICLE_PATH" ] || [ ! -f "$ARTICLE_PATH" ]; then
  echo "REJECTED: 找不到文章 $ARTICLE_PATH"
  exit 1
fi

CONTENT=$(cat "$ARTICLE_PATH")

# AI 常見開場句型（中文）
AI_OPENERS_ZH=(
  "在現代社會中"
  "隨著科技的發展"
  "在當今"
  "隨著時代的進步"
  "在資訊爆炸的"
  "科技日新月異"
  "深入了解"
  "值得注意的是"
  "透過本文"
  "讓我們一起探索"
  "全面掌握"
  "總結來說"
  "此外"
  "綜上所述"
)

# AI 常見開場句型（英文）
AI_OPENERS_EN=(
  "In today's world"
  "In the modern era"
  "As technology advances"
  "In this day and age"
  "With the rapid development"
  "In recent years"
  "It is worth noting"
  "Furthermore"
  "Moreover"
  "In conclusion"
  "It is important to mention"
)

# AI 常見自我誇讚
AI_SELF_PRAISE=(
  "這是一個很好的問題"
  "Great question"
  "Certainly"
  "Absolutely"
  "Of course"
  "當然可以"
)

# 檢查各類型
for pattern in "${AI_OPENERS_ZH[@]}"; do
  if echo "$CONTENT" | grep -q "$pattern"; then
    RESULT="REJECTED"
    AI_PATTERNS="$AI_PATTERNS\n- AI 中文句型：「$pattern」"
  fi
done

for pattern in "${AI_OPENERS_EN[@]}"; do
  if echo "$CONTENT" | grep -qi "$pattern"; then
    RESULT="REJECTED"
    AI_PATTERNS="$AI_PATTERNS\n- AI 英文句型：「$pattern」"
  fi
done

for pattern in "${AI_SELF_PRAISE[@]}"; do
  if echo "$CONTENT" | grep -qi "$pattern"; then
    RESULT="REJECTED"
    AI_PATTERNS="$AI_PATTERNS\n- AI 自我誇讚：「$pattern」"
  fi
done

# 輸出結果
if [ "$RESULT" = "APPROVED" ]; then
  echo "APPROVED: 未偵測到明顯 AI 痕跡"
else
  echo "REJECTED: 偵測到 AI 生成痕跡"
  echo -e "問題位置：$AI_PATTERNS"
  echo "請用更自然、直接的方式重寫這些部分"
fi
