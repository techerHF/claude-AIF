#!/usr/bin/env bash
# stop-test.sh
# 緊急停止測試腳本
# 用法：bash stop-test.sh
# 效果：
#   1. 建立 .stop-test 旗標 → 測試腳本下一輪開始前偵測並優雅退出
#   2. 列出目前殘留的 claude 進程
#   3. 詢問是否強制 kill 所有 claude 進程

cd ~/ai-factory 2>/dev/null || { echo "❌ 找不到 ~/ai-factory"; exit 1; }

echo ""
echo "🛑 ════════════════════════════════════════════════════════"
echo "🛑  AI 無人工廠 — 緊急停止"
echo "🛑 ════════════════════════════════════════════════════════"

# ── 建立停止旗標 ──
touch .stop-test
echo "✅ 已建立 .stop-test 旗標"
echo "   測試腳本將在當前 Batch 完成後、下一輪開始前停止"

# ── 顯示進度 ──
if [ -f logs/parallel-progress.json ]; then
  echo ""
  echo "── 目前進度 ──"
  python3 -c "
import json
d=json.load(open('logs/parallel-progress.json'))
print(f'  Cycle: {d.get(\"cycle\",\"?\")}/10')
print(f'  完成: {d.get(\"total_done\",\"?\")} 任務')
print(f'  通過: ✅{d.get(\"pass\",\"?\")}  失敗: ❌{d.get(\"fail\",\"?\")}')
print(f'  狀態: {d.get(\"status\",\"?\")}')
" 2>/dev/null || cat logs/parallel-progress.json
fi

# ── 列出殘留 claude 進程 ──
echo ""
echo "── 殘留 Claude 進程 ──"
CLAUDE_PROCS=$(pgrep -a claude 2>/dev/null || ps aux | grep claude | grep -v grep)
if [ -n "$CLAUDE_PROCS" ]; then
  echo "$CLAUDE_PROCS"
  echo ""
  echo "是否立即強制 Kill 所有 claude 進程？[y/N]"
  read -r -t 10 CONFIRM
  if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
    pkill -9 -f "claude" 2>/dev/null
    echo "✅ 已 Kill 所有 claude 進程"
  else
    echo "⏳ 跳過（等待測試腳本自然退出）"
  fi
else
  echo "  （無殘留 claude 進程）"
fi

echo ""
echo "提示：若要手動確認已停止，執行："
echo "  ps aux | grep claude | grep -v grep"
echo "  cat logs/parallel-progress.json"
