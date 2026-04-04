#!/usr/bin/env bash
# quality-check.sh
# 用途：主品質把關，驗證文章是否符合張旭豐思維框架
# 使用：bash quality-check.sh [文章路徑]
# 輸出：APPROVED 或 REJECTED（附說明）

set -euo pipefail

ARTICLE_PATH=$1
RESULT="APPROVED"
ISSUES=""

if [ -z "$ARTICLE_PATH" ] || [ ! -f "$ARTICLE_PATH" ]; then
  echo "REJECTED: 找不到文章檔案 $ARTICLE_PATH"
  exit 1
fi

CONTENT=$(cat "$ARTICLE_PATH")

# 檢查1：數字數量（至少3個）
# 用 { grep || true; } 避免 pipefail 在零比對時中止腳本
NUMBER_COUNT=$(echo "$CONTENT" | { grep -oE '[0-9]+\.?[0-9]*' || true; } | wc -l)
if [ "$NUMBER_COUNT" -lt 3 ]; then
  RESULT="REJECTED"
  ISSUES="$ISSUES\n- 數字不足：只有 $NUMBER_COUNT 個，至少需要3個"
fi

# 檢查2：英文禁止誇大詞
FORBIDDEN_EN=("revolutionary" "incredible" "amazing" "perfect" "magic" "best ever" "game changer")
for word in "${FORBIDDEN_EN[@]}"; do
  if echo "$CONTENT" | grep -qi "$word"; then
    RESULT="REJECTED"
    ISSUES="$ISSUES\n- 英文禁止詞：$word"
  fi
done

# 檢查3：中文禁止誇大詞
FORBIDDEN_ZH=("革命性" "驚人" "完美" "神奇" "最棒" "無敵" "超強")
for word in "${FORBIDDEN_ZH[@]}"; do
  if echo "$CONTENT" | grep -q "$word"; then
    RESULT="REJECTED"
    ISSUES="$ISSUES\n- 中文禁止詞：$word"
  fi
done

# 檢查4：論述結構關鍵要素（用 | 而非 \| 搭配 -E 旗標）
check_keyword() {
  local label=$1
  local pattern=$2
  if ! echo "$CONTENT" | grep -qiE "$pattern"; then
    RESULT="REJECTED"
    ISSUES="$ISSUES\n- 缺少論述要素：$label"
  fi
}

check_keyword "場景/問題"  "問題|場景|Problem|scenario|challenge|偵測|應用"
check_keyword "原理/機制"  "原理|機制|Principle|mechanism|because|因為|工作原理|如何運作"
check_keyword "步驟/材料"  "步驟|材料|Step|Material|零件|元件|接線|Components|接腳"
check_keyword "結果/驗證"  "結果|數據|Result|data|測試|驗證|Serial|輸出|實測|實驗"

# 檢查5：字數範圍
# 標準：純文字 800–1500 字 / 含程式碼總字數最多 5000 字
TOTAL_CHAR=$(echo "$CONTENT" | wc -m)
if [ "$TOTAL_CHAR" -lt 800 ]; then
  RESULT="REJECTED"
  ISSUES="$ISSUES\n- 字數不足：$TOTAL_CHAR 字，最少800字"
fi
if [ "$TOTAL_CHAR" -gt 5000 ]; then
  RESULT="REJECTED"
  ISSUES="$ISSUES\n- 字數過多：$TOTAL_CHAR 字（含程式碼），上限5000字"
fi

# 輸出結果
if [ "$RESULT" = "APPROVED" ]; then
  echo "APPROVED"
  echo "數字數量：$NUMBER_COUNT"
  echo "含程式碼總字數：$TOTAL_CHAR"
else
  echo "REJECTED"
  echo -e "問題清單：$ISSUES"
  echo "請根據以上問題修改後重新提交"
fi
