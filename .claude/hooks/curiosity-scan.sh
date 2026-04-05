#!/usr/bin/env bash
# 每週日 20:00：研究員主動學習最新技術趨勢
cd ~/ai-factory
mkdir -p ~/ai-factory/.knowledge

claude -p "
你是 researcher agent。今天是好奇心掃描日。

任務：掃描並學習以下技術趨勢：
1. 用 WebFetch 抓取 https://www.reddit.com/r/arduino/top.json?t=week&limit=15
   分析本週最熱 Arduino 話題
2. 用 WebFetch 抓取 https://www.reddit.com/r/esp32/top.json?t=week&limit=10
   分析 ESP32 本週趨勢
3. 找出 3 個「有人問但目前沒有好教學」的主題

讀取 .knowledge/lessons.md 了解已記錄的主題（避免重複）。

將發現 append 寫入 .knowledge/lessons.md（不要覆蓋既有內容）：
格式：
## 好奇心掃描 $(date +%Y-%m-%d)
- 發現：[主題] — [為什麼值得寫，一句話]
- 發現：[主題] — [為什麼值得寫，一句話]
- 發現：[主題] — [為什麼值得寫，一句話]
" \
  --dangerously-skip-permissions \
  --allowedTools "WebFetch,Read,Write,Bash" \
  --max-turns 15 2>&1
