# INA219 電流功率感測器：太陽能監控、電池管理的必備工具

做 Maker 的，難免會碰到一個問題：「我的太陽能板到底有沒有在充電？」或者「這顆鋰電池還剩多少電？」

老實說，用 Arduino 內建的 ADC 來量電流，誤差大到讓人想放棄。10-bit 解析度搭配 5V 範圍，每個刻度是 4.9mV。如果你的負載吃 20mA，用 0.1 歐姆 shunt，訊號只有 2mV——根本淹沒在 ADC 噪音裏。

## 為什麼這顆感測器值得學？

INA219 是 TI 的專用電流感測 IC，12-bit 解析度、內建 0.1 歐姆 shunt、直接 I2C 輸出。不只量電壓，還幫你算好電流和功率，無需自己在 Arduino 裏面換算數學。

重點是：**你終於可以準確看到系統的真實功耗**。之前用基本 ADC 量不到的微小漏電流（夜裡 0.8mA 那種），INA219 統統看得見。

實測數據（我的太陽能監控專案）：
- 陽光下充電電流：340mA（終於有數據了）
- 夜間漏電流：0.8mA（之前完全看不到）
- 找到了那顆故障的 USB 太陽能控制器，它晚上還在吃 50mA——這問題不找出來，電池遲早被慢性耗死

規格：
- 匯流排電壓：0-26V（夠應付大多數 maker 專案）
- 電流解析度：0.8mA（比 Arduino ADC 精 16 倍）
- I2C 通訊，ESP32 3.3V 完全相容

## 電路配置

```
Arduino ---- I2C ---- INA219 ---- 負載
                     |
                   0.1Ω shunt
```

程式碼只要幾行：

```cpp
#include <Wire.h>
#include <Adafruit_INA219.h>

Adafruit_INA219 ina219;

void setup() {
  Serial.begin(115200);
  ina219.begin();
  ina219.setCalibration_32V_1A(); // 一般專案夠用
}

void loop() {
  Serial.print("電壓: "); Serial.print(ina219.getBusVoltage_V()); Serial.println(" V");
  Serial.print("電流: "); Serial.print(ina219.getCurrent_mA()); Serial.println(" mA");
  Serial.print("功率: "); Serial.print(ina219.getPower_mW()); Serial.println(" mW");
  delay(500);
}
```

如果你的 shunt 不是 0.1 歐姆，或者要量超過 1A，可以用 `setCalibration(0.1, 3.0)` 自訂（第一個參數是歐姆數，第二個是最大電流）。

## 我的建議

如果你在做的專案有：
- 太陽能充電管理
- 電池電量監控
- 行動裝置功耗分析

一顆 INA219（大概 60 元）可以讓你從「靠感覺」升級到「有數據」。省下的除錯時間絕對值得。

想要完整的太陽能監控方案？[檢視我的 Whop 感測器指南]包含了電路圖、校正方法、以及常見問題的處理方式。

— 張旭豐，機械工程博士，業餘 Maker