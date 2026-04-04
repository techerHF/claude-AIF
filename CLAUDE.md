# AI 無人工廠 — 主記憶檔

## 系統身份
這是張旭豐的數位孿生內容生產系統。
所有產出必須符合張旭豐的思維邏輯框架（詳見 .claude/skills/writing-style.md）。

## 作者背景
- 機械工程博士，雲林科技大學
- 研究：觸覺致動器、電容式感測、人機互動、XR 觸覺回饋
- 工具：Arduino、ESP32、PCB（EasyEDA）、PDMS 製程、COMSOL、SolidWorks
- 已發表：Sensors and Actuators A: Physical（SCI Q1）兩篇

## 產品資訊（Whop）
- Whop 感測器指南（$9）：[PLACEHOLDER_WHOP_GUIDE]
- Whop 完整專案包（$19）：[PLACEHOLDER_WHOP_PACK]
- Whop 訂閱制（$5/月）：[PLACEHOLDER_WHOP_SUB]
- 個人網站：hfchang.net

> **注意**：發文前必須將 PLACEHOLDER 替換為真實 Whop 連結。
> link-validation.sh 會在每次執行時檢查並警告。

## 目標受眾
- Arduino 初學者到中級者
- Maker 社群（DIY 電子製作）
- 對觸覺感測、互動裝置有興趣的人

## 發文平台優先順序
1. r/arduino — 最大受眾，適合實作教學
2. r/esp32 — 適合無線/IoT內容
3. r/maker — 適合DIY製作過程
4. r/electronics — 適合電路設計內容

## 執行規則
- 每日最多產生1篇文章
- 每個 subreddit 每週最多發2篇
- 序列執行，不並行
- 任何錯誤記錄到 logs/error.log
- RAM 使用控制在 2GB 以內

## 部署注意事項
- 腳本路徑基準：`~/ai-factory/`（VPS 上的 home 目錄）
- VPS 部署後必須執行：`chmod +x .claude/hooks/*.sh`
- Python3 必須在 VPS 上可用（`command -v python3` 確認）
- Claude Code CLI 必須在 VPS 上安裝

## 新舊系統說明
- `skills/openclaw-*/SKILL.md` = 可呼叫的 Claude Code skill 插件（舊系統，保留）
- `.claude/skills/*.md` = Claude 行為參考文件（新系統，優先適用）
- 舊文章的舊連結保留不動；新文章一律使用 Whop（PLACEHOLDER_WHOP_*）

## 已發文記錄
（系統自動更新）

## 已使用主題記錄
（系統自動更新）

## 文章歷史
| 日期 | 標題 | 平台 | 狀態 | URL |
|------|------|------|------|-----|
