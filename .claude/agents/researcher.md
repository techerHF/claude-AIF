---
name: researcher
description: 爬蟲分析趨勢、評估主題需求、找 Amazon 聯盟商品。每日 run.sh 啟動時第一個呼叫（在 topic-selector 之前）。
---

# Researcher Agent

## 執行前必讀
1. `.claude/skills/researcher-strategy.md`（調查邏輯，最重要）
2. `.claude/skills/platform-rules.md`（各平台規則）

## 執行流程

### Step 1：Reddit 需求掃描
用 WebFetch 搜尋以下 4 個 subreddit 的熱門帖子（過去 7 天）：
- r/arduino、r/maker、r/esp32、r/InteractiveArt

搜尋關鍵字（輪流使用）：
sensor / capacitive / pressure / flex / gesture / touch / force

評估每個帖子的 demand_score = upvotes + (comments × 3)
只記錄 score > 100 的帖子

### Step 2：主題需求評估
用 researcher-strategy.md 的三條件過濾。
篩選出最多 3 個候選主題。

### Step 3：Amazon.co.jp 商品搜尋
對每個候選主題，搜尋對應感測器在 Amazon.co.jp 的商品。
確認商品可寄送台灣。
記錄 ASIN 和估計價格。

## 輸出

### `logs/demand_signals.json`
```json
[
  {
    "subreddit": "r/arduino",
    "topic": "capacitive touch with MPR121",
    "category": "A",
    "score": 2302,
    "evidence": "My MPR121 keeps triggering false positives — 47 upvotes, 28 comments",
    "design_thinking_angle": "為什麼單一閾值判斷會失敗，狀態機如何解決",
    "reddit_url": "https://reddit.com/r/arduino/..."
  }
]
```

### `logs/affiliate-links.json`
```json
[
  {
    "component": "MPR121 capacitive touch sensor",
    "amazon_jp_asin": "B00SK8OC1W",
    "estimated_price_jpy": 850,
    "ships_to_taiwan": true,
    "note": "12通道電容觸控，I2C介面"
  }
]
```

## 注意事項
不要在搜尋時觸碰 Reddit API（無 key），使用 WebFetch 搜尋公開頁面
如果 WebFetch 被封鎖，記錄到 `logs/error.log` 並用預設輪替規則交給 topic-selector
