#!/usr/bin/env bash
# 每天 08:00、16:00、00:00 執行 Standup
# 由 crontab 觸發，輸出到 logs/standup.log
cd ~/ai-factory

HOUR=$(date +%H)
SLOT="${HOUR}:00"
DATE=$(date +%Y-%m-%d)
LOG=".team-memory/standup-log.md"

claude -p "
你是 AI 無人工廠的 chief-of-staff。現在是 ${DATE} ${SLOT} Standup。

讀取以下檔案了解系統當前狀態：
1. logs/progress.json — 今日執行進度
2. logs/daily.log — 讀取最後 50 行
3. .team-memory/standup-log.md — 讀取最後 20 行（了解上一次 standup 記錄）
4. .knowledge/performance.md — 文章表現數據

根據這些資料，回答三個問題：
1. 過去8小時完成了什麼？（具體說，不要說「完成了任務」）
2. 接下來8小時要做什麼？（具體說，不要說「繼續執行」）
3. 有沒有阻礙需要老闆決定？（有就說清楚，沒有就寫「無」）

用以下格式輸出，然後用 Bash 將內容 append 到 ${LOG}（絕對不要覆蓋檔案）：
[${DATE} ${SLOT}] Standup
- ✅ 完成：[具體事項]
- 🎯 下一步：[具體計畫]
- ⚠️ 阻礙：[無 / 具體問題]

如果有阻礙，另外執行：
bash ~/ai-factory/.claude/hooks/telegram-notify.sh \"⚠️ Standup 阻礙：[問題摘要]\"
" \
  --allowedTools "Read,Write,Bash" \
  --max-turns 15 2>&1
