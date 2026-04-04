---
name: monetization-strategy
description: 完整變現漏斗邏輯，從 Reddit 到 Whop 的四階段推出策略與各平台連結規則
type: behavioral
---

# 變現漏斗完整邏輯

## 漏斗架構

```
Reddit（英文）→ Medium（英中文）→ Whop 轉換
                                    ↓
                    $9   單篇深度指南
                    $19  完整專案包
                    $5/月 訂閱制
                    + Amazon 聯盟行銷（嵌在材料清單）
```

## 各層產品定價
- $9：單篇深度指南（一個感測器的完整設計思考）
- $19：完整專案包（多感測器 + 狀態機設計）
- $5/月：訂閱制（每月新主題）
- Amazon 聯盟：每篇材料清單最多5個連結，嵌入自然

## 各平台連結放置規則

### Reddit
- 主文：絕對不放 Whop 連結（會被 ban）
- 留言第一則：可以放，固定格式：
  「For anyone wanting the full design framework with state machine examples — I wrote it up here: [Whop 連結]」
- Amazon 聯盟：不放（Reddit 不允許）

### Medium
- 正文第七層（進階應用）：放一個 Whop 連結
- 材料清單：每個元件名稱加 Amazon 聯盟連結，最多5個
- 文末：可重複放 Whop 連結（第二次）

### 產品頁面（Whop）
- 標題：不超過60字
- 描述：500–800字，用 persona.md 語氣
- 不放 Reddit 主文連結（避免被認為是廣告）

## 產品推出四個階段

### 階段1：Reddit 跑通（0元收入，建立信任）
條件：至少5篇文章在 Reddit 有互動（upvotes > 20）
使用的 Skills：writing-style, article-structure, reddit-post
不動 Whop，不動變現邏輯

### 階段2：上架第1層（$9 指南）
條件：Reddit 上有讀者在留言問「更多資源」或「有沒有更詳細的」
動作：
  - 建立 Whop 產品頁面（whop-product.md）
  - 在最新一篇文章的 Reddit 第一留言加 Whop 連結
  - 在對應的 Medium 文章放連結

### 階段3：上訂閱（$5/月）
條件：至少3個人購買過第1層
動作：
  - 建立訂閱制頁面
  - 用 discount-pricing.md 設定訂閱者專屬優惠
  - 現有讀者是第一批告知對象

### 階段4：上第2層（$19 專案包）
條件：有訂閱者，且訂閱者持續續訂
動作：
  - 訂閱者是第一批買家（85折）
  - 用 discount-pricing.md 設定 Early Access 定價

## Amazon 聯盟行銷嵌入規則
- 每篇文章材料清單，每個元件名稱後加聯盟連結
- 格式：「Arduino UNO × 1（[Amazon](聯盟連結)）」
- 最多5個連結，不是每個零件都加（選常購買的）
- 禁止在標題或文章開頭放聯盟連結
- 禁止在 Reddit 任何地方放 Amazon 聯盟連結
