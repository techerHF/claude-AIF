---
name: openclaw-publisher
description: |
  OpenClaw 的發文 Skill。
  當需要「發文」「發布文章」「上傳到 DEV.to」「publish」「送出文章」時，必須啟動此 Skill。
  此 Skill 在 openclaw-editor 給出通過裁決後執行，
  自動將文章發布到 DEV.to（使用 API），並輸出格式化好的 Medium 版本供手動貼上。
  只要涉及「文章發布」「DEV.to 發文」「publish 到平台」，都必須使用此 Skill。
  流程：openclaw-editor 通過 → openclaw-publisher。
---

# OpenClaw Publisher Skill

## 功能定位

接收審稿通過的文章，自動發布到 DEV.to，並輸出 Medium 版本。

---

## Pipeline 位置

```
openclaw-editor（審稿通過）
  → publisher（你，發文）← 你在這裡
```

---

## 執行流程

### Step 1：確認輸入

收到文章後確認以下資訊都齊全：
- 文章標題
- 文章正文（Markdown，DEV.to 版本）
- 封面圖 URL（Openverse 圖片連結）
- Tags（最多 4 個，DEV.to 格式：英文小寫，不含 #）
- Wokwi 連結是否已填入（`[Wokwi 專案連結]` 占位有沒有被替換）
- Amazon 連結是否已填入
- Whop 連結是否已填入

如果有任何占位符還沒被替換，先告知用戶補齊再繼續。

### Step 2：準備發文 payload

把文章格式化成 DEV.to API 需要的 JSON：

```json
{
  "article": {
    "title": "[文章標題]",
    "body_markdown": "[文章正文，Markdown 格式]",
    "published": false,
    "tags": ["tag1", "tag2", "tag3"],
    "main_image": "[封面圖 URL]",
    "description": "[文章摘要，1-2 句話，從文章第一段提取]"
  }
}
```

注意：先用 `"published": false` 發為草稿，讓用戶確認 DEV.to 上的預覽後再發布。

### Step 3：發文到 DEV.to

把 payload 存成暫存 JSON 檔，然後用 curl 發送：

```bash
# 把 payload 存成暫存檔
cat > /tmp/devto_article.json << 'EOF'
{
  "article": {
    "title": "...",
    "body_markdown": "...",
    "published": false,
    "tags": [...],
    "main_image": "...",
    "description": "..."
  }
}
EOF

# 發送到 DEV.to API
curl -s -X POST "https://dev.to/api/articles" \
  -H "Content-Type: application/json" \
  -H "api-key: ${DEVTO_API_KEY}" \
  -d @/tmp/devto_article.json
```

成功回應會包含：
- `id`：文章 ID
- `url`：文章草稿 URL（格式：`https://dev.to/username/article-slug`）

### Step 4：確認草稿

把草稿 URL 告知用戶，請他：
1. 打開 URL 確認預覽
2. 確認 Wokwi embed 是否正常顯示
3. 確認所有連結正確
4. 確認後回覆「可以發布」

### Step 5：正式發布

收到確認後，用 PATCH 更新文章狀態為已發布：

```bash
curl -s -X PUT "https://dev.to/api/articles/[ARTICLE_ID]" \
  -H "Content-Type: application/json" \
  -H "api-key: ${DEVTO_API_KEY}" \
  -d '{"article": {"published": true}}'
```

### Step 6：輸出 Medium 版本

把 Medium 版本整理好輸出，讓用戶手動貼到 Medium：

```
## Medium 版本（手動貼上）

[在 Medium 新文章頁面，把以下內容貼上]

非會員可以透過這個連結免費閱讀：[Medium 朋友連結]

---

[文章正文，與 DEV.to 版本相同，但 Wokwi embed 改成直接放 URL]

注意：
- Wokwi URL 直接貼在接線步驟下方，Medium 會自動嵌入
- 封面圖在 Medium 裡單獨上傳（不在正文裡）
```

---

## 設定

### DEV.to API Key

API key 存放在環境變數 `DEVTO_API_KEY`。

設定方式（在 D:/openclaw/.env 裡加上）：
```
DEVTO_API_KEY=你的API_KEY
```

或在執行前直接 export：
```bash
export DEVTO_API_KEY=你的API_KEY
```

**不要把 API key 寫進任何文章、SKILL.md 或 git 追蹤的檔案裡。**

---

## 錯誤處理

| 錯誤碼 | 原因 | 處理方式 |
|--------|------|---------|
| 401 | API key 錯誤或過期 | 確認 DEVTO_API_KEY 設定正確 |
| 422 | 文章格式有問題 | 檢查 title 或 body_markdown 是否有問題 |
| 429 | 超過速率限制（10 篇/30 秒） | 等 30 秒後重試 |
| 500 | DEV.to 伺服器問題 | 等幾分鐘後重試 |

---

## Tags 建議

技術文章常用 tags（DEV.to 格式）：

| 主題 | 建議 tags |
|------|----------|
| Arduino 感測器 | `arduino`, `electronics`, `iot`, `tutorial` |
| PIR 感測器 | `arduino`, `sensor`, `electronics`, `beginners` |
| 互動裝置 | `electronics`, `arduino`, `interactivedesign`, `maker` |
| 繁體中文文章 | `arduino`, `tutorial`, `electronics`, `programming` |

DEV.to 最多 4 個 tag，用英文小寫，不含空格。
