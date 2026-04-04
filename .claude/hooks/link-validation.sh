#!/usr/bin/env bash
# link-validation.sh
# 用途：確認 Payhip 連結不是 PLACEHOLDER
# 使用：bash link-validation.sh
# 注意：只警告，不阻止產文；發文時才阻止

set -euo pipefail

CLAUDE_MD=~/ai-factory/CLAUDE.md

if [ ! -f "$CLAUDE_MD" ]; then
  echo "WARNING: 找不到 $CLAUDE_MD"
  exit 0
fi

# 檢查是否有 PLACEHOLDER
if grep -q "PLACEHOLDER" "$CLAUDE_MD"; then
  PLACEHOLDER_LINES=$(grep -n "PLACEHOLDER" "$CLAUDE_MD")
  echo "WARNING: 以下連結尚未填入真實 URL："
  echo "$PLACEHOLDER_LINES"
  echo ""
  echo "請在 CLAUDE.md 中填入真實的 Payhip 連結後再執行發文。"
  echo "目前可以繼續產文和審查，但發文步驟會跳過。"
  exit 2  # exit 2 = 警告但不阻止
fi

# 確認 Payhip 連結存在
if grep -q "payhip.com" "$CLAUDE_MD"; then
  PAYHIP_LINKS=$(grep "payhip.com" "$CLAUDE_MD")
  echo "APPROVED: 找到 Payhip 連結"
  echo "$PAYHIP_LINKS"
  exit 0
fi

echo "WARNING: CLAUDE.md 中沒有找到 Payhip 連結"
exit 2
