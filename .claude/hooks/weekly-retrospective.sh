#!/usr/bin/env bash
# weekly-retrospective.sh
# 每週一 08:00 由 cron 觸發
# 讓 chief-of-staff 子 agent 真實主持週會、產生週報、發 Telegram

cd ~/ai-factory
WEEK=$(date +%Y-W%V)
LOG=~/ai-factory/logs/retrospective.log

echo "[$(date)] 開始週報 $WEEK" >> "$LOG"

claude -p "
使用 Agent tool 呼叫 chief-of-staff 子 agent，主持本週回顧會議。

今天是 $(date +%Y-%m-%d)，第 $(date +%V) 週。

任務說明給 chief-of-staff：
1. 讀取以下所有資料：
   - logs/progress.json（本週發文）
   - .knowledge/performance.md（成效數據，若存在）
   - .knowledge/lessons.md（本週學習，若存在）
   - .team-memory/experiments.md（實驗進度）
   - .team-memory/proposals.md（待審提案）
   - .agent-growth/*.md（各 agent 成長）

2. 更新 .team-memory/weekly-retrospective.md（append，不覆蓋）：
   格式：
   ## 週報 $(date +%Y-W%V)（$(date +%Y-%m-%d)）
   ### 本週數據
   - 產出文章：X 篇
   - 系統運行：正常/有問題
   ### 做得好的事
   - [具體說明]
   ### 需要改善的事
   - [具體說明根本原因]
   ### 各 Agent 亮點
   - researcher：[本週發現]
   - writer：[本週成長]
   ### 下週建議
   - 優先主題類別：
   - 實驗計畫：

3. 更新 .team-memory/okr-tracking.md 的當前進度數字

4. 整理 proposals.md 中待審核的提案，產生摘要

5. 發 Telegram 週報：
   bash .claude/hooks/telegram-notify.sh '📊 第$(date +%V)週週報
產出：X篇 | 成效：待確認
提案：X個待你審核
需要決策：[最重要1-2項]
詳細報告：cat .team-memory/weekly-retrospective.md'
" \
  --allowedTools "Agent,Read,Write,Bash" \
  --max-turns 10 2>&1 | tee -a "$LOG"

echo "[$(date)] 週報完成" >> "$LOG"
