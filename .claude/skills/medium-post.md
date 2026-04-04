---
name: medium-post
description: Medium 發文 SOP，英中文版時序、字數、Whop 連結放置規則、Tags 設定
type: behavioral
---

# Medium 發文 SOP

## 發文時序
英文版先發，中文版後發（間隔 2 小時）。
兩個版本同一天發，讓 Medium 演算法把它們視為不同文章。

## 文章長度要求
Medium Partner Program 收益門檻：150 字以上（我們遠超過）
英文版目標：1500 字以上（含程式碼）
中文版目標：1200 字以上（含程式碼）

## Reddit 版 vs Medium 版差異
Reddit 版：600–900 字，問題+解法+數據，結尾說「Full write-up in the comments」
Medium 版：1500+ 字，七層完整結構展開，Whop 連結放這裡

Medium 版不能是 Reddit 版的直接擴展——要重新詮釋，加入 Reddit 版沒說的設計思考。

## Whop 連結放置規則
只放在第七層「進階應用」段落末尾。
一篇文章只放一個 Whop 連結（不重複）。

英文版文案：
「If you want the complete multi-sensor design framework —
including three interaction scenarios and state machine templates —
I put it all in a design guide. [Whop 連結], $9.」

中文版文案：
「如果想要完整的多感測器設計框架——
包含三種互動場景和狀態機模板——
我把它整理成一份設計指南。[Whop 連結]，$9。」

## Amazon 聯盟連結放置
材料清單每個元件名稱後加 Amazon.co.jp 聯盟連結。
格式：`- Arduino UNO × 1（[Amazon](聯盟連結)）：主控制器`
最多 5 個連結，選讀者最可能購買的元件。
文章最開頭或標題附近必須放免責聲明：
「*As an Amazon Associate I earn from qualifying purchases.*」

## Tags 設定（Medium SEO）
每篇文章設定 5 個 tags：
1. Arduino
2. [主題感測器名稱，如 Capacitive Sensor]
3. Maker
4. Interactive Design
5. DIY Electronics

中文版另加：[主題的中文關鍵字，如 電容式感測器]

## 發文後必做
把文章 URL 記錄到 `.knowledge/posted-articles.md`
格式：`| YYYY-MM-DD | 標題 | Medium | published | - | URL |`

## 無法自動發文的說明
Medium 沒有官方發文 API。
系統產出的是 `.md` 格式文章，需手動貼到 Medium 編輯器。
建議流程：
1. 用 VS Code 開啟 `.md` 檔
2. 複製全文貼到 Medium 草稿
3. 手動加入 Amazon 聯盟連結（需要在 Amazon 後台產生）
4. 確認 Tags 和封面圖後發布
