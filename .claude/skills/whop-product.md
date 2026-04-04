---
name: whop-product
description: Whop 產品頁面結構、三層產品寫法差異、標題公式、Early Access 定價文案
type: behavioral
---

# Whop 產品頁面結構

## 三層產品的標題公式
格式：[感測器名稱] + [設計問題] + [成果數字]
範例：
- $9 指南：「Capacitive Pressure Sensor — Why Your Threshold Logic Fails, and a 3-State Design That Doesn't」
- $19 專案包：「Tactile Sensor Array — 4×4 Grid + State Machine, 0–50 kPa, Full Arduino Source」
- $5/月：「Tactile Design Monthly — One Sensor, One Design Decision, Per Month」

## 產品頁面結構（每層相同框架）

### 第1區：問題確認（2–3句）
讓讀者說「對，這就是我遇到的問題」
不介紹自己，不說背景，直接說問題

### 第2區：這份指南包含什麼（條列，4–6項）
具體說明讀者會學到什麼設計決策
不說「完整教學」，說「你會看到為什麼 FSR 的電阻值不是問題，狀態機才是」

### 第3區：適合誰
說清楚適合什麼程度的人
「會寫 Arduino，想從接線跨到設計思考的人」

### 第4區：不適合誰
誠實說排除對象
「如果你只需要一個讀值，這份不適合你——YouTube 有更快的教學」

### 第5區：一句話承諾
具體成果，不說「學好感測器」
說「讀完你可以解釋為什麼同一個感測器在兩個設計裡表現不同」

## 產品描述語氣規則
用 persona.md 的語氣：直接、有觀點、不過度謙虛
禁止詞：「全面」「完整」「最好」「必備」「一定要」
禁止問句開場：「你是否曾經...？」（陳腔濫調）
禁止承諾數字：「學完你的感測器精度提升80%」（無法驗證）

## Early Access 定價文案
時機：新產品上架前72小時，訂閱者專屬
格式：
「Early Access for subscribers — $7 instead of $9, for 72 hours.
This is the flex sensor design framework I've been testing for 3 months.
[Whop 連結]」

禁止：
「限時特價！！！」
「倒數計時！搶購！」

## 各層頁面字數建議
$9 指南：400–600字
$19 專案包：600–800字
$5/月 訂閱：300–400字（月費訂閱決策快，不需要說太多）
