---
name: feedback-interpretation
description: 解讀 Reddit 互動數據的邏輯，判斷高/中/低表現，觸發策略調整的條件
type: behavioral
---

# 解讀 Reddit 互動數據

## 什麼數據有意義

### 高互動信號（需要記錄並學習）
- upvotes > 30：標題和主題都對了
- comments > 10：讀者有問題 = 有購買意圖
- 有人問「哪裡可以買材料」：直接購買信號，立刻在留言放 Amazon 聯盟連結
- 有人問「有沒有更完整的版本」：Whop 轉換信號，立刻在留言放 Whop 連結

### 低互動信號（需要分析原因）
upvotes < 5 且 comments < 3 且發文超過 48 小時：
可能原因（按優先順序排查）：
1. 標題沒有鉤子（最常見）
2. 主題在這個 subreddit 沒需求（試換平台）
3. 發文時機不好（考慮週二–週四 UTC 18:00–22:00 發）
4. 帳號 karma 不夠，被過濾（查 Reddit 帳號狀態）

## 解讀優先順序
1. **留言內容 > upvote 數量**
   有人問問題比只是讚更有價值
2. **前 6 小時互動 > 總互動**
   Reddit 演算法在前 6 小時決定能見度；前 6 小時沒反應，後續很難回升
3. **問題型留言 > 讚美型留言**
   問題代表需求，讚美代表滿意但不一定轉換

## 表現分類標準
高表現：upvotes ≥ 20 或 comments ≥ 8
中表現：upvotes 5–19 且 comments 3–7
低表現：upvotes < 5 且 comments < 3（48 小時後）

## 什麼情況下調整策略
- 同一主題類別連續 3 篇低表現 → 換主題類別，至少跳過 2 週
- 同一鉤子公式連續失效 2 次 → 換鉤子公式（參考 topic-hook.md）
- 特定 subreddit 持續低互動 → 先停一週，分析其他帖子的規律

## 留言回覆策略
收到問題型留言時：
1. 在 2 小時內回覆（趁熱）
2. 直接回答問題，不帶推銷語氣
3. 若問題涉及 Whop 指南的內容，最後一句：
   「I cover this in more depth here → [Whop 連結]」

收到讚美型留言時：
1. 簡短道謝
2. 問一個問題（增加 comment 數）：「What's your current setup? Are you using a threshold or something else?」

## 回饋到 writing-style.md 的格式
在「已驗證有效模式」區塊加入：
```
### YYYY-MM-DD 驗證
標題格式：[格式描述]
主題類別：[A/B/C/D]
upvotes：X / comments：Y
有效原因：[分析]
下次應用：[具體建議]
```
