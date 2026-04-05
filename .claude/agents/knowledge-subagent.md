---
name: knowledge-subagent
description: 每次任務結束前強制更新知識庫。Stop Hook 觸發，確保記錄不遺漏。只讀寫，不產生文章。
allowed_tools: ["Read", "Write", "Bash"]
---

# Knowledge Subagent

## 執行前必讀
1. `.claude/skills/knowledge-update.md`（更新 SOP，最重要）

## 觸發時機
1. run.sh 正常結束時（自動呼叫）
2. 任務途中發生錯誤，Stop Hook 觸發時
3. 主動呼叫：`claude -p "呼叫 knowledge-subagent"`

## 每次必須執行的三個步驟

### Step 1：更新 `.knowledge/posted-articles.md`
讀取 `logs/progress.json` 中今日的發文記錄。
如果有新文章，加到 `.knowledge/posted-articles.md` 表格中。
狀態設為 `reviewed`（審查完但還沒真的發文）。

### Step 2：更新 `CLAUDE.md` 文章歷史
在 CLAUDE.md 底部的「文章歷史」表格加入今日記錄：
```
| 今日日期 | 文章標題 | 平台 | reviewed | - |
```

### Step 3：更新 `logs/progress.json`
確認今日記錄的 status 欄位為 `reviewed`。
如果 progress.json 中有 status 為空的記錄，補上。

## 如果沒有今日文章
檢查 `logs/error.log` 是否有今日的錯誤記錄。
如果有，把錯誤摘要加到 `.knowledge/lessons.md`：
```
YYYY-MM-DD 任務失敗：[錯誤摘要]
原因：[從 error.log 讀取]
下次處理：[建議]
```

## 完成後輸出格式
```
knowledge-subagent 完成：
  - posted-articles.md：+1 筆記錄
  - CLAUDE.md：文章歷史已更新
  - progress.json：status 已確認
```
