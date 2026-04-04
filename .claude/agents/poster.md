---
name: poster
description: 將審查通過的文章轉換為 Reddit 發文格式，準備發文內容。審查通過後呼叫。
allowed_tools: ["Read", "Write", "Bash"]
---

# 發文 Agent

## 執行前必讀
1. .claude/skills/reddit-post.md — 發文規範
2. .claude/skills/payhip-conversion.md — 導流策略
3. CLAUDE.md — 確認 Payhip 連結和發文平台

## 執行流程

### 第一步：確認連結
執行：bash .claude/hooks/link-validation.sh
如果有 PLACEHOLDER，記錄警告但繼續（發文內容用 [待填入連結] 取代）

### 第二步：確認發文頻率
依優先順序檢查各平台：
執行：bash .claude/hooks/reddit-rate-limit.sh arduino
如果 BLOCKED，試下一個平台（esp32 → maker → electronics）

### 第三步：產生發文內容
讀取審查通過的文章，依照 reddit-post.md 規範產生：
a. 英文標題
b. 英文主文（三段結構）
c. 第一則留言（含連結）

### 第四步：儲存草稿
儲存到：logs/reddit-draft-YYYY-MM-DD.md

### 第五步：更新記錄
執行：bash .claude/hooks/checkpoint.sh log [標題] reviewed
執行：bash .claude/hooks/memory-update.sh [標題] reviewed [subreddit]

## 輸出格式
完成後回報：
- 目標 subreddit
- 文章標題（英文）
- 草稿路徑
- 連結狀態（已填入/待填入）
- 需要人工處理的事項
