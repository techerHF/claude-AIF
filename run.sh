#!/usr/bin/env bash
# AI 無人工廠主控制腳本
# 執行：bash ~/ai-factory/run.sh
# 自動觸發：cron 每日 09:00

set -euo pipefail

cd ~/ai-factory
TODAY=$(date +%Y-%m-%d)
LOG_FILE=~/ai-factory/logs/daily.log
ERROR_LOG=~/ai-factory/logs/error.log

mkdir -p ~/ai-factory/logs

{
  echo "=============================="
  echo "執行時間：$(date)"
  echo "=============================="
} >> "$LOG_FILE"

# 前置檢查
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 未安裝" | tee -a "$ERROR_LOG"; exit 1; }
command -v claude >/dev/null 2>&1 || { echo "ERROR: claude CLI 未安裝" | tee -a "$ERROR_LOG"; exit 1; }

# ── 步驟0：爬蟲需求偵測（openclaw-scraper）──────────────────────────
echo "[step0] 啟動 openclaw-scraper..." | tee -a "$LOG_FILE"

claude -p "
你是 openclaw-scraper。讀取 skills/openclaw-scraper/SKILL.md 後執行以下任務：

掃描以下 subreddit 的今日熱門貼文（過去24小時）：
r/arduino, r/esp32, r/maker, r/electronics

使用 WebFetch 抓取每個 subreddit：
URL 格式：https://www.reddit.com/r/{subreddit}/top.json?t=day&limit=10
Headers：User-Agent: ResearchBot/1.0

解析後，計算每個貼文的需求分數：score = upvotes + (comments × 3)
按照 SKILL.md 的關鍵字表識別主題類別（A/B/C/D）。

將結果寫入 logs/demand_signals.json（格式見 SKILL.md）。
最後輸出一行摘要：掃描完成，最高需求主題和分數。
" \
  --allowedTools "WebFetch,Write,Read" \
  --permission-mode acceptEdits \
  --max-turns 15 2>> "$LOG_FILE"

echo "[step0] 爬蟲完成" | tee -a "$LOG_FILE"
# ────────────────────────────────────────────────────────────────────

claude -p "
你是 AI 無人工廠主控 Agent。今日日期：$TODAY。

在開始之前，請讀取以下檔案：
1. CLAUDE.md
2. .claude/skills/writing-style.md
3. logs/demand_signals.json （爬蟲需求信號，今日剛產生）

然後按照以下步驟序列執行（每步完成才進行下一步）：

【步驟1：確認今日狀態】
執行：bash .claude/hooks/checkpoint.sh today-done
如果輸出是 1，輸出「今日任務已完成，結束執行」然後停止。
如果輸出是 0，繼續執行。

【步驟2：選題】
呼叫 topic-selector agent 決定今日主題。
記錄選定主題和標題。

【步驟3：產文】
呼叫 writer agent，傳入選定主題。
確認文章已儲存到 articles/ 資料夾。

【步驟4：SEO 優化】
呼叫 seo-agent 優化標題和關鍵字。
如果有優化建議，更新文章標題。

【步驟5：品質審查】
呼叫 reviewer agent 審查文章。

如果 REJECTED：
  - 記錄退回原因
  - 呼叫 writer agent 依照退回建議修改（最多修改2次）
  - 第3次仍然失敗：
    執行：bash .claude/hooks/checkpoint.sh log [主題] failed
    輸出「品質審查失敗，需要人工處理」然後停止

如果 APPROVED：
  繼續步驟6

【步驟6：準備發文內容】
呼叫 poster agent 產生 Reddit 發文草稿。
草稿路徑：logs/reddit-draft-$TODAY.md

【步驟7：更新所有記錄】
執行：bash .claude/hooks/checkpoint.sh log [文章標題] reviewed
執行：bash .claude/hooks/memory-update.sh [文章標題] reviewed [目標subreddit]

【步驟8：輸出今日摘要】
輸出以下資訊：
=== 今日執行摘要 ===
文章標題：[標題]
文章路徑：[路徑]
字數：[字數]
審查結果：通過（第幾次）
目標平台：r/[subreddit]
草稿路徑：[路徑]
連結狀態：[已填入/待填入]
需要人工處理：[是/否，如果是說明原因]

重要限制：
- 序列執行，每步完成才進行下一步
- 任何錯誤記錄到 $ERROR_LOG 並繼續嘗試下一步
- RAM 使用控制，不並行執行
" \
  --allowedTools "Write,Read,Bash,Agent" \
  --permission-mode acceptEdits \
  --max-turns 50 2>> "$LOG_FILE"

echo "執行完畢：$(date)" >> "$LOG_FILE"
