---
name: openclaw-editor
description: |
  OpenClaw 的審稿 Skill。
  當需要「審稿」「文章品質把關」「review 文章」「給修改建議」「編輯文章」時，必須啟動此 Skill。
  此 Skill 讓多個不同角色的 reviewer agent 從各自的專業角度審查一篇文章，
  各自給出修訂建議與裁決，最後由 manager agent 彙整所有意見給出最終裁決。
  只要涉及「文章送審」「品質確認」「writer 完成後的下一步」「editor 審稿」，都必須使用此 Skill。
  openclaw-writer 完成文章後，下一步就是送到 openclaw-editor。
---

# OpenClaw Editor Skill

## 功能定位

Writer 完成文章後，這個 skill 讓五個不同角色的 reviewer 分別檢查文章，從自己的專業角度提出具體的修改建議，並給出裁決。所有 reviewer 完成後，manager 彙整全部意見給出最終裁決與行動指引。

這不是一個人把文章看一遍，而是五個不同的視角依序或並行地檢查同一篇文章。

---

## Pipeline 位置

```
writer（產出文章）
  → editor（你，審稿）← 你在這裡
  → publisher（確認通過後發布）
```

---

## 執行流程

### Step 1：確認輸入

收到文章後確認：
- 文章語言（中文 / 英文）
- 受眾層級（初階 / 中階 / 高階）
- 文章主題

### Step 2：依序啟動五個 reviewer

每個 reviewer 各自獨立審查文章，從自己的角度提出意見。
在 Claude.ai 環境（無 subagent），依序進行，一個完成再下一個。
在 Claude Code 環境（有 subagent），可並行執行。

---

## 五個 Reviewer 角色

### Reviewer 1：技術準確性審稿

**審查重點：**
- 技術數據是否正確（電壓、範圍、角度、波長等）
- 程式碼是否可以執行，有沒有語法錯誤或邏輯錯誤
- 元件型號、規格描述是否符合實際
- 原理說明是否有技術上的錯誤或過度簡化導致誤導

**輸出格式：**
```
## 技術準確性審稿

### 裁決
[Reject / Revise and resubmit / Accept with minor revisions / Accept in its present form]

### 問題清單
1. [問題描述，引用文章原文，說明為什麼有問題]
2. ...

### 修改建議
1. [具體的修改方式]
2. ...
```

---

### Reviewer 2：語氣與風格審稿

**審查重點：**
- 有沒有 AI 感語句（「深入了解」「值得注意的是」「透過本文」等）
- 有沒有破折號
- 句子是否夠短、夠直接
- 是否符合張旭豐語氣風格（帶讀者一起想，不是告訴讀者答案）
- 有沒有抽象開頭或學術式結構語句
- 操作感是否足夠（讀者是否能跟著做）

**輸出格式：**
```
## 語氣與風格審稿

### 裁決
[Reject / Revise and resubmit / Accept with minor revisions / Accept in its present form]

### 問題清單
1. [問題描述，引用文章原文，說明違反了哪條語氣規則]
2. ...

### 修改建議
1. 原文：「...」
   建議改成：「...」
2. ...
```

---

### Reviewer 3：轉換率審稿

**審查重點：**
- Amazon 連結是否置入兩次（第一次提到元件 + 材料清單）
- Whop 單品 CTA 說法是否正確（賣執行步驟和 project pack，不是材料）
- Whop 會員 CTA 說法是否正確（賣持續 access，不是一次買斷）
- 心癢設計是否夠具體（進化方向是否列出 2-3 個具體可能性）
- CTA 出現的時機和語氣是否自然，不像推銷
- 讀者看完是否會想繼續做，是否有清楚的下一步

**輸出格式：**
```
## 轉換率審稿

### 裁決
[Reject / Revise and resubmit / Accept with minor revisions / Accept in its present form]

### 問題清單
1. [問題描述]
2. ...

### 修改建議
1. [具體改法]
2. ...
```

---

### Reviewer 4：SEO 審稿

**審查重點：**
- 標題是否包含主要關鍵字
- 文章中是否自然出現目標關鍵字（不是硬塞）
- H2 標題是否能反映讀者可能搜尋的問題
- 文章是否覆蓋了受眾可能搜尋的主要問題（對應 openclaw-researcher 的受眾需求報告，如果有的話）
- 段落開頭是否有足夠的關鍵字密度

**輸出格式：**
```
## SEO 審稿

### 裁決
[Reject / Revise and resubmit / Accept with minor revisions / Accept in its present form]

### 問題清單
1. [問題描述]
2. ...

### 修改建議
1. [具體改法]
2. ...
```

---

### Reviewer 5：讀者體驗審稿

**審查重點：**
- 初階讀者是否能真正跟著做，每個步驟是否清楚
- 買到材料後的第一個動作是否明確
- 程式碼之後是否有「你應該看到什麼」的說明
- 是否有常見問題 + 預設解答
- 完成後的樣子是否有具體描述，讓讀者知道成功是什麼感覺
- 心癢段落的進化方向，讀者是否能感覺「這些我也想做」

**輸出格式：**
```
## 讀者體驗審稿

### 裁決
[Reject / Revise and resubmit / Accept with minor revisions / Accept in its present form]

### 問題清單
1. [問題描述]
2. ...

### 修改建議
1. [具體改法]
2. ...
```

---

## Manager Agent：最終裁決

所有 reviewer 完成後，manager 負責：

1. 彙整所有裁決
2. 判斷整體裁決（以最嚴格的裁決為基準）
3. 整理出必須改的問題（Reject 或 Revise 的理由）和建議改的問題（minor revisions）
4. 給 writer 一份清楚的行動清單

**最終裁決標準：**

| 狀況 | 最終裁決 |
|------|---------|
| 任何一個 reviewer 給出 Reject | Reject |
| 沒有 Reject，但有 Revise and resubmit | Revise and resubmit |
| 全部是 minor revisions 或更好 | Accept with minor revisions |
| 全部是 Accept in its present form | Accept in its present form |

**Manager 輸出格式：**
```
## 最終裁決

### 整體裁決
[Reject / Revise and resubmit / Accept with minor revisions / Accept in its present form]

### 必須修改（發布前）
1. [來自哪個 reviewer] [問題描述] [建議改法]
2. ...

### 建議修改（可選）
1. [來自哪個 reviewer] [問題描述] [建議改法]
2. ...

### 總結
[1-2 句說明這篇文章目前的狀態和最重要的改進方向]
```

---

## 裁決定義

| 裁決 | 意思 | Writer 需要做什麼 |
|------|------|-----------------|
| Reject | 有根本性問題，需要大幅重寫 | 重寫後重新送審 |
| Revise and resubmit | 有明確問題需要修改，修改後需重新審查 | 修改後送回 editor |
| Accept with minor revisions | 整體可以，有幾個小地方需要調整 | 調整後可直接發布，不需重審 |
| Accept in its present form | 可以直接發布 | 送到 publisher |
