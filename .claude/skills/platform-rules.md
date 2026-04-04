---
name: platform-rules
description: 各平台（Reddit/Medium/Whop/Amazon）發文規則、限制與合規要求
type: behavioral
---

# 各平台規則與限制

## Reddit 規則
帳號需求：30 天以上歷史，新帳號容易被過濾
發文間隔：同一 subreddit 至少間隔 3 天
每日上限：同一天只發一篇（跨 subreddit 也算）
商業連結：主文絕對不放 Whop 或 Amazon 聯盟連結
連結位置：只在發文後的第一則自己的留言放
標題禁詞：buy / shop / sale / discount / cheap / affiliate
Karma 門檻：部分 subreddit（r/arduino）要求最低 karma 才能發文

各 subreddit 特別規則：
- r/arduino：每週 2 篇上限（我們系統已控制）
- r/maker：允許 showcase，鼓勵附圖片或影片
- r/esp32：偏好有 IoT/無線功能的內容
- r/electronics：偏好電路設計深度，不歡迎純 Arduino 教學

## Medium 規則
Partner Program 收益：文章需 150 字以上，且必須是會員可讀
重複內容：同一篇文章不能和 Reddit 版幾乎相同（需有差異化）
外部圖片：需標注授權來源（使用 CC0 圖片或自製圖片）
聯盟連結：允許 Amazon 聯盟連結，但需在文章中聲明
無發文 API：目前只能手動貼到 Medium 編輯器

## Whop 規則
產品描述：不能有誤導性承諾（如「保證讓你的精度提升 X%」）
退款政策：需在產品頁面清楚說明（建議：7 天無理由退款）
定價一致性：數位產品發布後不建議頻繁改價（影響早期買家信任）
Early Access：折扣需要有明確截止時間

## Amazon 聯盟規則（Amazon.co.jp Associates）
免責聲明：文章中必須出現（建議放在文章開頭或材料清單前）：
「*As an Amazon Associate I earn from qualifying purchases.*」
連結限制：不能在 Reddit 任何地方放聯盟連結
偽裝禁止：聯盟連結不能用短網址偽裝（要讓讀者看得出來是 Amazon）
台灣讀者：使用 Amazon.co.jp（日本站），台灣可直送
連結有效期：聯盟連結不會過期，但商品下架後需要更新

## 跨平台內容複製規則
Reddit → Medium：可以，但 Medium 版要更完整（1.5–2 倍篇幅）
Medium → 其他平台：不建議，Medium 有重複內容偵測
同一篇文章不能在兩個不同 subreddit 完全相同發布

## 帳號安全規則
不在工具或程式碼中硬編碼 Reddit/Medium 密碼
Whop 帳號啟用二步驟驗證
API 金鑰存在環境變數，不存在程式碼或文章中
