---
name: knowledge-update
description: 知識庫更新 SOP，每次任務結束必須執行的四個檔案更新規則
type: behavioral
---

# 知識庫更新 SOP

## 知識庫位置
```
.knowledge/
├── posted-articles.md    ← 發文歷史（每篇文章一行）
├── performance.md        ← 成效記錄（feedback-collector 更新）
├── lessons.md            ← 踩坑記錄（遇到問題就記）
└── good-titles.md        ← 高效標題（upvotes > 10 才收錄）
```

## 每次任務結束必須更新

### 1. posted-articles.md（writer 完成後立刻更新）
表格格式：
```
| 日期 | 標題 | 平台 | 狀態 | upvotes | 備註 |
|------|------|------|------|---------|------|
| 2026-04-04 | 自製電容式壓力感測器 | r/arduino | reviewed | - | 待發文 |
```
狀態值：`reviewed`（審查完）→ `posted`（已發文）→ `tracked`（已收集回饋）

### 2. performance.md（feedback-collector 在發文 24 小時後更新）
格式：
```
2026-04-04：自製電容式壓力感測器 | r/arduino | upvotes:47 | comments:15 | 表現:高
分析：標題含三個數字，前6小時得到23 upvotes，觸發演算法加速
```

### 3. lessons.md（遇到問題就立刻記，不等任務結束）
格式：
```
2026-04-04 踩坑：quality-check 在 grep 零比對時 pipefail 中止
原因：set -euo pipefail 下 grep 無匹配 exit 1 導致 pipeline 失敗
解法：改用 { grep ... || true; } 包裹
下次避免：所有用 grep 計數的地方都要加 || true 保護
```

### 4. good-titles.md（upvotes > 10 才收錄，低於此不記）
格式：
```
[47] 自製電容式壓力感測器：0–20 kPa，材料只要 85 元 | 2026-04-04 | r/arduino
[35] 5-finger flex sensor glove with ESP32 — reads 0-90° bend | 2026-04-05 | r/maker
```

## 強制執行機制
knowledge-subagent 在每次 run.sh 結束前執行。
如果沒有更新 `.knowledge/posted-articles.md`，任務視為未完成。
Stop Hook 攔截並強制呼叫 knowledge-subagent。

## CLAUDE.md 同步更新
每次發文後，更新 CLAUDE.md 底部的「文章歷史」表格：
```
| 2026-04-04 | 自製電容式壓力感測器 | r/arduino | reviewed | - |
```

## 路徑說明
本地開發：`.knowledge/` 在 repo root
VPS 部署：`~/ai-factory/.knowledge/`
兩者都使用 Git 追蹤，確保 VPS 和本地同步
