#!/usr/bin/env bash
# curiosity-scan.sh
# 每週日 20:00 由 cron 觸發
# 讓 researcher 子 agent 真實執行主動學習任務
cd ~/ai-factory
mkdir -p ~/ai-factory/.knowledge

claude -p "
使用 Agent tool 呼叫 researcher 子 agent，執行本週好奇心掃描任務。

任務說明給 researcher：
1. 掃描 r/arduino 和 r/esp32 本週熱門帖（WebFetch JSON endpoint）
2. 找出 3 個「有需求但缺好教學」的主題
3. 掃描 r/MachineLearning 或 HN（Hacker News top）找本週 AI 工具新動態
4. 分析任何新工具是否能改善工廠流程（不限，開放探索）
5. 把發現 append 寫入 .knowledge/lessons.md，格式：
   ## 好奇心掃描 YYYY-MM-DD
   - 發現：[主題] — [為什麼值得寫，一句話]
6. 如果發現值得討論的新工具或策略，寫進 .team-memory/proposals.md：
   ## 提案-[日期]-[標題]
   提案者：researcher
   類型：新工具/新方法
   核心價值：[一句話]
   建議行動：A/B測試 / 直接採用 / 觀察一個月
7. 更新 .agent-growth/researcher.md 的「本月好奇心發現」欄位
8. 如果有新提案，執行：bash .claude/hooks/telegram-notify.sh '💡 研究員有新提案待審核，請查看 proposals.md'
" \
  --allowedTools "Agent,Read,Write,WebFetch,Bash" \
  --max-turns 8 2>&1
