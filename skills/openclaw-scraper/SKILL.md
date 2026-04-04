# openclaw-scraper

## 用途
掃描 Reddit 熱門貼文，輸出需求信號供 topic-selector 使用。
每日 run.sh 啟動時自動執行（步驟0）。

## 觸發條件
- run.sh 步驟0 呼叫
- 或手動：`/openclaw-scraper`

## 執行工具
- WebFetch：抓取 Reddit JSON API
- Bash：寫入 logs/demand_signals.json

## 掃描目標
| Subreddit | 用途 |
|-----------|------|
| r/arduino | 主要受眾，實作教學 |
| r/esp32 | IoT/無線相關 |
| r/maker | DIY 製作社群 |
| r/electronics | 電路設計受眾 |

## 執行流程

### 1. 抓取每個 subreddit 的 top posts（過去24小時）

API 端點格式：
```
https://www.reddit.com/r/{subreddit}/top.json?t=day&limit=10
```
Headers: `User-Agent: ResearchBot/1.0`

### 2. 解析貼文資料

從 JSON 中提取：
- `data.children[].data.title` — 標題
- `data.children[].data.score` — upvotes 數
- `data.children[].data.num_comments` — 留言數
- `data.children[].data.subreddit` — 板名

### 3. 關鍵字匹配

將標題與以下關鍵字比對，識別主題類別：

| 關鍵字 | 主題 | 類別 |
|--------|------|------|
| pressure, force, capacitive | 壓力感測 | A |
| bend, flex, resistive | 彎曲感測 | A |
| gesture, motion, hand | 手勢辨識 | B |
| password, secure, keypad | 密碼安全 | B |
| PCB, schematic, layout | PCB 設計 | C |
| signal, noise, filter, amplify | 訊號處理 | C |
| PDMS, silicone, elastic | 材料製作 | D |
| copper foil, electrode | 電極製作 | D |

### 4. 計算需求分數

```
score = upvotes + (comments × 3)
```

留言比 upvotes 更能代表「有問題想解決」的需求。

### 5. 輸出格式

寫入 `logs/demand_signals.json`：

```json
[
  {
    "subreddit": "r/arduino",
    "post_title": "How do I read capacitive sensors without noise?",
    "upvotes": 847,
    "comments": 63,
    "score": 1036,
    "topic": "電容式感測",
    "category": "A",
    "scraped_at": "2026-04-04T09:00:12"
  }
]
```

## 注意事項

- Reddit API 有速率限制：每分鐘 60 次請求
- 每個 subreddit 間隔 2 秒避免被封
- 若 API 回傳 429，等待 60 秒後重試一次
- 若抓取失敗，寫入空陣列 `[]`，讓 topic-selector 改用歷史輪替邏輯

## 輸出確認

成功後輸出：
```
[scraper] 掃描完成：4 個 subreddit，共 40 篇貼文
[scraper] 最高需求：壓力感測 (score: 2528, r/maker)
[scraper] 結果寫入：logs/demand_signals.json
```
