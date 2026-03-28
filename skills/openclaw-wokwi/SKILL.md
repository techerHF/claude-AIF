---
name: openclaw-wokwi
description: |
  OpenClaw 的 Wokwi 電路圖生成 Skill。
  當需要「生成電路圖」「產出 Wokwi 接線圖」「建立 diagram.json」「製作互動式模擬器」「在文章裡嵌入接線圖」時，必須啟動此 Skill。
  此 Skill 根據元件清單和接線關係，自動產出符合 Wokwi 格式的 diagram.json，
  讓作者只需貼上 JSON 即可在 Wokwi 建立可模擬、可嵌入文章的互動式電路圖。
  只要涉及「Wokwi 電路」「接線圖」「互動模擬」「電路視覺化」，都必須使用此 Skill。
  通常在 openclaw-writer 產出文章草稿後呼叫，為文章的實作段落產出電路圖。
---

# OpenClaw Wokwi Skill

## 功能定位

根據文章的元件清單和接線關係，產出：
1. `diagram.json`，可以直接貼進 Wokwi 建立電路
2. 一份簡單的建立步驟說明，告訴作者怎麼從 diagram.json 拿到公開的 Wokwi 連結

產出的連結可以嵌入到 DEV.to（用 `{% embed URL %}`）和 Medium（直接貼 URL）。

---

## 重要說明：Wokwi API 的限制

Wokwi CI token 用途是讓 CI 管道呼叫 Wokwi 雲端模擬器跑測試，**不是建立或發布新公開專案**。
目前沒有官方 REST API 可以程式化建立公開的 Wokwi 專案連結。

所以這個 skill 的角色是：
- 自動完成最難的部分（寫 diagram.json）
- 作者只需要做最後一步：把 JSON 貼進 Wokwi，複製 URL，貼到文章

---

## 執行流程

### Step 1：確認輸入
- 電路主題（例如：HC-SR501 PIR 感測器 + Arduino Uno + 內建 LED）
- 元件清單（型號 + 數量）
- 接線關係（哪個腳位接哪個腳位）

如果輸入不完整，查看文章草稿，自行從實作段落提取元件和接線資訊。

### Step 2：查詢元件 type name

使用以下已知的 Wokwi type name：

| 元件 | Wokwi type | 常用腳位 |
|------|-----------|---------|
| Arduino Uno | `wokwi-arduino-uno` | `5V`, `3.3V`, `GND.1`, `GND.2`, `1`~`13`（數位），`A0`~`A5`（類比） |
| Arduino Nano | `wokwi-arduino-nano` | 同上 |
| Arduino Mega | `wokwi-arduino-mega` | 同上，更多腳位 |
| PIR 動作感測器（HC-SR501）| `wokwi-pir-motion-sensor` | `VCC`, `GND`, `OUT` |
| LED | `wokwi-led` | `A`（正極）, `K`（負極） |
| 電阻 | `wokwi-resistor` | `1`（一端）, `2`（另一端） |
| 蜂鳴器（有源）| `wokwi-buzzer` | `1`（正）, `2`（負） |
| 超聲波感測器 HC-SR04 | `wokwi-hc-sr04` | `VCC`, `TRIG`, `ECHO`, `GND` |
| I2C LCD 1602 | `wokwi-lcd1602` | `SDA`, `SCL`, `VCC`, `GND` |
| 麵包板 | `wokwi-breadboard` | 不需要，通常直接接 Arduino |

如果遇到不在清單內的元件，先搜尋 `https://docs.wokwi.com/parts/[元件名稱]` 確認 type name 和腳位名稱。

### Step 3：產出 diagram.json

使用以下格式：

```json
{
  "version": 1,
  "author": "OpenClaw",
  "editor": "wokwi",
  "parts": [
    {
      "type": "[wokwi type name]",
      "id": "[元件id，例如 uno, pir1, led1]",
      "top": [y座標，整數，元件之間間隔約 100-200px],
      "left": [x座標，整數],
      "attrs": {}
    }
  ],
  "connections": [
    ["[來源id]:[腳位名稱]", "[目標id]:[腳位名稱]", "[顏色]", []]
  ]
}
```

**顏色慣例：**
- 紅色（`"red"`）：VCC / 正電
- 黑色（`"black"`）：GND / 接地
- 綠色（`"green"`）：訊號線
- 黃色（`"yellow"`）：其他訊號線
- 藍色（`"blue"`）：SDA / 資料線
- 橙色（`"orange"`）：SCL / 時脈線

**座標建議：**
- Arduino Uno 放在中間偏右，`top: 50, left: 200`
- 感測器放在左側，`top: 0, left: -100`
- LED 或輸出元件放在右側

### Step 4：確認 diagram.json 正確性

檢查：
- 每個 connection 的 id 和腳位名稱是否存在（對照 Step 2 的腳位清單）
- VCC 和 GND 都有接
- 訊號線的腳位對應文章程式碼裡設定的腳位號碼

### Step 5：輸出

產出三樣東西：

1. `diagram.json` 檔案內容（可以直接複製）
2. 對應的 `sketch.ino` 程式碼（如果文章裡有，直接引用；如果沒有，根據電路產出基礎版本）
3. 建立 Wokwi 專案的步驟說明（每次都附上，3 步以內）

---

## 輸出格式

```
## diagram.json

[完整的 JSON 內容，可直接複製]

---

## sketch.ino

[完整的 Arduino 程式碼]

---

## 建立 Wokwi 專案（3 步）

1. 前往 https://wokwi.com，點右上角「New Project」，選「Arduino Uno」
2. 點左側面板的「diagram.json」分頁，把上面的 JSON 全部貼上覆蓋原有內容
3. 點右上角「Share」，複製專案 URL，貼回文章的 [Wokwi 專案連結] 位置

完成後：
- DEV.to 文章：在接線位置加上 `{% embed [你的 Wokwi URL] %}`
- Medium 文章：直接把 Wokwi URL 貼在接線說明後面，Medium 會自動嵌入
```

---

## PIR 感測器 + Arduino Uno 標準模板

這是 HC-SR501 + Arduino Uno + 內建 LED 的標準 diagram.json，可以直接使用：

```json
{
  "version": 1,
  "author": "OpenClaw",
  "editor": "wokwi",
  "parts": [
    {
      "type": "wokwi-arduino-uno",
      "id": "uno",
      "top": 50,
      "left": 200,
      "attrs": {}
    },
    {
      "type": "wokwi-pir-motion-sensor",
      "id": "pir1",
      "top": 0,
      "left": -50,
      "attrs": {}
    }
  ],
  "connections": [
    ["pir1:VCC", "uno:5V", "red", []],
    ["pir1:GND", "uno:GND.1", "black", []],
    ["pir1:OUT", "uno:2", "green", []]
  ]
}
```

注意：LED_PIN 13 是 Arduino Uno 的板載 LED，不需要外接，所以電路圖只需要 PIR 感測器和 Arduino 本體。

---

## 常見的接線錯誤

- `GND.1` 和 `GND.2` 是 Arduino Uno 的兩個 GND 腳位，兩個都可以用
- Arduino Uno 的數位腳位在 connections 裡直接用數字，例如 D2 寫成 `"uno:2"`
- PIR 的 `OUT` 腳位輸出 HIGH 時代表偵測到動作，這點和程式碼裡的 `digitalRead(PIR_PIN) == HIGH` 對應
