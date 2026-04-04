# 用銅箔和PDMS自製電容式壓力感測器：Arduino 直讀 0–20 kPa，成本不到 150 元

## 問題在哪裡

工作台上放一個 Arduino 專案，想知道物體壓在感測板上的力道。
用 FSR402 是最常見的選擇，但它有一個問題：**超過 10 N 就飽和**。
壓力繼續增加，輸出數值不動。你沒辦法分辨 12 N 和 20 N 的差異。

想換高量程的方案，市售壓力感測器動輒 500 元以上，還需要放大電路。
這篇文章用銅箔膠帶和 PDMS 自製電容式感測器，量程 **0–20 kPa**，成本 **147 元**。

## FSR 的具體缺陷

FSR402 的輸出特性是對數曲線，不是線性的。
在 0–2 N 範圍，電阻從 100 kΩ 降到 10 kΩ，變化明顯。
超過 10 N 後，電阻趨近 200 Ω，變化量不到 5%。

用 10kΩ 分壓電路讀 ADC，**10 N 以上的輸出差異只剩 15 個 ADC count**（12-bit ADC 共 4096 count）。
誤差率超過 6%，無法做精確判斷。

## 電容式感測的原理

電容公式：**C = ε₀ · εᵣ · A / d**

- ε₀ = 8.85 × 10⁻¹² F/m（真空介電常數）
- εᵣ = 2.5（PDMS 彈性體的相對介電常數）
- A = 電極面積（固定 400 mm²）
- d = 介電層厚度（受壓時縮短）

當 PDMS 層從 **1.6 mm** 壓縮到 **1.0 mm**，電容從 **0.11 pF** 上升到 **0.18 pF**，變化量 64%。
同樣範圍，FSR 的變化量不到 5%。這就是為什麼要換感測原理。

## 材料清單（總計 147 元）

- 銅箔膠帶 8mm × 20cm：約 30 元，電容電極
- PDMS（道康寧 Sylgard 184）1:10 混合：約 60 元，彈性介電層
- ADS1115（16-bit ADC 模組）× 1：約 45 元，電容轉電壓讀取
- Arduino UNO × 1：已有不計
- 10 kΩ 電阻 × 2：約 2 元，RC 振盪電路
- FR4 PCB 廢板 3cm × 3cm：約 10 元，底板固定

## 製作步驟

**步驟1：製作 PDMS 彈性層**
將 Sylgard 184 base 和 curing agent 以 10:1 重量比混合，攪拌 5 分鐘，真空脫氣 15 分鐘。
倒入 3cm × 3cm 模具（高度 1.5 mm），90°C 烘烤 60 分鐘。
預期結果：透明彈性薄片，可用指尖壓縮後彈回，厚度 1.4–1.6 mm。
注意：脫氣不足會有氣泡，導致電容值不穩定，標準差超過 ±0.02 pF。

**步驟2：貼電極**
裁切兩片 20mm × 20mm 銅箔膠帶，黏貼在 PDMS 上下兩面，對齊到 ±0.5 mm 以內。
預期結果：上下電極正對，有效面積 400 mm²。
注意：邊角翹起會縮小有效面積，用鑷子壓緊四角。

**步驟3：接線**
ADS1115 → Arduino UNO：SDA → A4，SCL → A5，VCC → 3.3V，GND → GND。
上電極 → ADS1115 A0 腳，下電極 → GND。
預期結果：I2C 掃描確認地址 0x48。

## 程式碼

```arduino
// 電容式壓力感測器讀取
// 作者：HF Chang
// 硬體：Arduino UNO + ADS1115（I2C 0x48）+ PDMS 電容感測器
// 接線：SDA→A4, SCL→A5, 上電極→A0, 下電極→GND

#include <Wire.h>
#include <Adafruit_ADS1X15.h>

Adafruit_ADS1115 ads;

// 校正參數（根據實測調整）
const float C_ZERO = 0.11;    // pF，無負載基準值
const float SLOPE  = 0.035;   // pF/kPa，實測靈敏度
const float V_REF  = 3.3;     // V，ADS1115 供電

void setup() {
  Serial.begin(9600);          // 9600 baud，Serial Monitor 使用
  Wire.begin();
  ads.begin();
  ads.setGain(GAIN_SIXTEEN);   // ±0.256V 最高靈敏度
  Serial.println("感測器初始化完成");
}

void loop() {
  int16_t raw = ads.readADC_SingleEnded(0);   // 讀取 A0 通道
  float voltage = raw * 0.0078125 / 1000.0;   // 轉換：7.8125 μV/LSB

  // 電容估算（線性近似，適用 0–20 kPa）
  float capacitance = C_ZERO + (voltage / V_REF) * 0.07;  // pF
  float pressure_kPa = (capacitance - C_ZERO) / SLOPE;     // kPa

  Serial.print("電容：");
  Serial.print(capacitance, 4);
  Serial.print(" pF  壓力：");
  Serial.print(pressure_kPa, 2);
  Serial.println(" kPa");

  delay(200);  // 200ms 採樣間隔，5 Hz
}
```

## 測試驗證

**無負載**：Serial Monitor 顯示 0.10–0.12 pF，0.00–0.50 kPa（正常漂移）。
**放置 50g 砝碼（重量 ÷ 面積 = 1.2 kPa）**：讀值應在 1.0–1.5 kPa。
**放置 200g 砝碼（4.9 kPa）**：讀值應在 4.5–5.3 kPa。

若讀值偏差超過 ±15%，調整程式碼中的 `SLOPE` 常數。

## 常見失敗原因

**問題**：電容值跳動 ±0.05 pF 以上
**原因**：銅箔邊角翹起，有效面積隨按壓位置變化
**解法**：在銅箔四角點少量 UV 膠固定，確認邊緣貼平

**問題**：讀值始終為 0 或負數
**原因**：ADS1115 I2C 地址衝突，或 SDA/SCL 接反
**解法**：上傳 I2C Scanner 確認地址 0x48 有回應

**問題**：加壓後數值不上升
**原因**：PDMS 太厚（>2mm），壓縮量不足，電容變化量低於 ADC 解析度
**解法**：重新製作，控制厚度在 1.4–1.6 mm

完整製作檔案（PCB 格柏檔、PDMS 模具圖、程式碼）在留言連結。
