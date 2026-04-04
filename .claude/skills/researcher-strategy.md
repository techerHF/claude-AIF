---
name: researcher-strategy
description: 研究員調查邏輯，市場需求評估三條件、資料來源優先順序、輸出格式
type: behavioral
---

# 研究員調查邏輯

## 任務定義
每次產文循環開始前，確認本週主題有真實市場需求。
不是「感覺很熱門」，是「有人在問但沒人完整回答」。

## 資料來源優先順序
1. Reddit（r/arduino, r/maker, r/esp32, r/InteractiveArt）← 最直接的需求信號
2. Stack Overflow（有人卡住但沒好答案的問題）
3. GitHub Issues（開源函式庫的常見問題）

## 主題評估三個條件（全部符合才推薦）
1. **需求存在**：有人在問但沒有完整好答案
   → 找到的帖子 upvotes > 20，且留言有「I've been struggling with this too」類的回應
2. **定位符合**：跟互動設計、觸覺、感測或人機互動有連結
   → 不只是「接線教學」，要有設計決策的空間
3. **作者加分**：博士觸覺/感測背景能讓這篇比一般教學更深
   → 如果任何人都能寫出一樣的文章，這個主題不夠好

## 評分公式
demand_score = upvotes + (comments × 3)
score > 500 → 高需求（主題驅動選題）
score 200–500 → 中需求（需結合輪替規則）
score < 200 → 低需求（除非符合所有三條件否則跳過）

## Reddit 爬蟲搜尋關鍵字
一級關鍵字（直接需求）：
- sensor fails / sensor not working
- how to detect / how to measure
- threshold / debounce / calibration
- capacitive / pressure / flex / force sensing
- gesture recognition / touch detection

二級關鍵字（設計問題）：
- state machine / finite state
- interrupt vs polling
- noise / drift / stability
- latency / response time

## 輸出格式
`logs/demand_signals.json`：
```json
[
  {
    "subreddit": "r/arduino",
    "topic": "主題名稱",
    "category": "A/B/C/D",
    "score": 2302,
    "evidence": "找到的具體問題或帖子標題",
    "design_thinking_angle": "從哪個設計角度切入",
    "reddit_url": "帖子 URL（若有）"
  }
]
```

主題分類：
- A = 電容式/觸壓感測
- B = 手勢辨識/彎曲感測
- C = 互動設計/狀態機
- D = IoT/ESP32/無線

## Amazon 商品同步研究
找到主題後，同時搜尋 Amazon.co.jp 對應感測器。
輸出 `logs/affiliate-links.json`：
```json
[
  {
    "component": "FSR 402",
    "amazon_jp_asin": "BXXXXXXXX",
    "estimated_price_jpy": 1200,
    "ships_to_taiwan": true,
    "note": "可選備用型號：FSR 406（更大感測面積）"
  }
]
```
